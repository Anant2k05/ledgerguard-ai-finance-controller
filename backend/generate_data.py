import random
from datetime import date, timedelta

from dotenv import load_dotenv
from supabase import create_client

import os

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

random.seed(42)

merchants = [
    "Amazon",
    "Flipkart",
    "Swiggy",
    "Zomato",
    "Myntra",
    "Uber",
    "BookMyShow",
    "Croma",
    "BigBasket",
    "MakeMyTrip",
]

start_date = date(2026, 8, 1)

transactions = []
settlements = []

for i in range(1, 151):

    transaction_id = f"TXN-{i:04d}"
    transaction_date = start_date + timedelta(days=random.randint(0, 30))
    amount = round(random.uniform(200, 15000), 2)

    transactions.append({
        "transaction_id": transaction_id,
        "transaction_date": transaction_date.isoformat(),
        "merchant": random.choice(merchants),
        "amount": amount,
        "currency": "INR",
        "payment_status": "paid",
    })

    # Create different reconciliation scenarios
    scenario = random.choices(
        [
            "exact_match",
            "amount_mismatch",
            "missing_settlement",
            "date_mismatch",
            "duplicate",
            "fee_mismatch",
        ],
        weights=[65, 10, 7, 6, 5, 7],
        k=1,
    )[0]

    if scenario == "missing_settlement":
        continue

    settlement_amount = amount
    settlement_date = transaction_date + timedelta(days=random.randint(1, 3))
    fee = round(amount * 0.02, 2)

    if scenario == "amount_mismatch":
        settlement_amount = round(amount - random.uniform(50, 500), 2)

    elif scenario == "date_mismatch":
        settlement_date = transaction_date + timedelta(days=random.randint(7, 12))

    elif scenario == "fee_mismatch":
        fee = round(amount * 0.05, 2)

    settlements.append({
        "settlement_id": f"SET-{i:04d}",
        "transaction_id": transaction_id,
        "settlement_date": settlement_date.isoformat(),
        "settled_amount": settlement_amount,
        "fee": fee,
        "status": "settled",
    })

    if scenario == "duplicate":
        settlements.append({
            "settlement_id": f"SET-DUP-{i:04d}",
            "transaction_id": transaction_id,
            "settlement_date": settlement_date.isoformat(),
            "settled_amount": settlement_amount,
            "fee": fee,
            "status": "settled",
        })


print("Uploading transactions...")

supabase.table("transactions").insert(transactions).execute()

print("Uploading settlements...")

supabase.table("settlements").insert(settlements).execute()

print(f"Inserted {len(transactions)} transactions.")
print(f"Inserted {len(settlements)} settlements.")