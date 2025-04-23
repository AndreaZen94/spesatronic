from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime
import json
import os

app = Flask(__name__)
app.secret_key = 'expense_splitter_secret_key'

# File to store expenses data
DATA_FILE = 'expenses.json'


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {"expenses": [], "people": []}


def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)


def calculate_balances(data):
    people = data["people"]
    expenses = data["expenses"]

    # Initialize balances
    balances = {person: 0 for person in people}

    # Calculate what each person has paid and what they owe
    for expense in expenses:
        payer = expense["paid_by"]
        amount = float(expense["amount"])
        split_among = expense["split_among"]

        if not split_among:  # If no one selected, split among all
            split_among = people

        split_amount = amount / len(split_among)

        # Add the full amount to what the payer paid
        balances[payer] += amount

        # Subtract what each person owes
        for person in split_among:
            balances[person] -= split_amount

    return balances


def calculate_settlements(balances):
    # Create a list of (person, balance) tuples
    balance_list = [(person, balance) for person, balance in balances.items()]

    # Sort by balance (debtors first, creditors last)
    balance_list.sort(key=lambda x: x[1])

    settlements = []
    i, j = 0, len(balance_list) - 1

    while i < j:
        debtor, debt = balance_list[i]
        creditor, credit = balance_list[j]

        if abs(debt) < credit:
            # Debtor pays their full debt to creditor
            settlements.append({
                "from": debtor,
                "to": creditor,
                "amount": round(abs(debt), 2)
            })
            balance_list[j] = (creditor, credit + debt)  # Reduce creditor's credit
            i += 1
        else:
            # Debtor pays part of their debt to creditor
            settlements.append({
                "from": debtor,
                "to": creditor,
                "amount": round(credit, 2)
            })
            balance_list[i] = (debtor, debt + credit)  # Reduce debtor's debt
            j -= 1

    return settlements


@app.route('/')
def index():
    data = load_data()
    balances = calculate_balances(data)
    settlements = calculate_settlements(balances)

    return render_template('index.html',
                           data=data,
                           balances=balances,
                           settlements=settlements)


@app.route('/add_person', methods=['POST'])
def add_person():
    data = load_data()
    new_person = request.form['person_name'].strip()

    if new_person and new_person not in data["people"]:
        data["people"].append(new_person)
        save_data(data)
        flash(f"Added {new_person} to the group!")
    elif not new_person:
        flash("Person name cannot be empty!")
    else:
        flash(f"{new_person} is already in the group!")

    return redirect(url_for('index'))


@app.route('/remove_person/<person>')
def remove_person(person):
    data = load_data()
    if person in data["people"]:
        data["people"].remove(person)

        # Remove person from split_among lists in expenses
        for expense in data["expenses"]:
            if person in expense["split_among"]:
                expense["split_among"].remove(person)

            # If this person paid for an expense, mark it as "removed user"
            if expense["paid_by"] == person:
                expense["paid_by"] = "removed user"

        save_data(data)
        flash(f"Removed {person} from the group!")

    return redirect(url_for('index'))


@app.route('/add_expense', methods=['POST'])
def add_expense():
    data = load_data()

    description = request.form['description'].strip()
    amount = request.form['amount'].strip()
    paid_by = request.form['paid_by']
    split_among = request.form.getlist('split_among')

    if not description or not amount or not paid_by:
        flash("Please fill in all required fields!")
        return redirect(url_for('index'))

    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError("Amount must be positive")
    except ValueError:
        flash("Please enter a valid positive amount!")
        return redirect(url_for('index'))

    new_expense = {
        "id": len(data["expenses"]),
        "description": description,
        "amount": amount,
        "paid_by": paid_by,
        "split_among": split_among,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    data["expenses"].append(new_expense)
    save_data(data)
    flash(f"Added expense: {description}")

    return redirect(url_for('index'))


@app.route('/remove_expense/<int:expense_id>')
def remove_expense(expense_id):
    data = load_data()

    for i, expense in enumerate(data["expenses"]):
        if expense["id"] == expense_id:
            removed = data["expenses"].pop(i)
            save_data(data)
            flash(f"Removed expense: {removed['description']}")
            break

    return redirect(url_for('index'))


@app.route('/reset')
def reset():
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)
    flash("Reset all data!")
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)