from ai_investigator import investigate_exception


exception = {
    "transaction_id": "TXN-TEST",
    "exception_type": "amount_mismatch",
    "expected_amount": 5000,
    "actual_amount": 4500
}

transaction = {
    "transaction_id": "TXN-TEST",
    "transaction_date": "2026-08-15",
    "merchant": "Amazon",
    "amount": 5000,
    "currency": "INR",
    "payment_status": "paid"
}

settlement = {
    "settlement_id": "SET-TEST",
    "transaction_id": "TXN-TEST",
    "settlement_date": "2026-08-17",
    "settled_amount": 4500,
    "fee": 100,
    "status": "settled"
}


result = investigate_exception(
    exception,
    transaction,
    settlement
)

print("\n=== AI INVESTIGATION ===")
print(result)