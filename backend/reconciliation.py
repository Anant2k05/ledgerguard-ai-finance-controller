from datetime import date
from collections import Counter


def reconcile_transactions(transactions, settlements):
    """
    Compare payment transactions against settlement records.

    Returns:
        results: list of reconciliation results
        summary: aggregate metrics
    """

    settlement_map = {}

    for settlement in settlements:
        transaction_id = settlement["transaction_id"]

        if transaction_id not in settlement_map:
            settlement_map[transaction_id] = []

        settlement_map[transaction_id].append(settlement)

    results = []

    for transaction in transactions:
        transaction_id = transaction["transaction_id"]
        expected_amount = float(transaction["amount"])
        transaction_date = date.fromisoformat(
            transaction["transaction_date"]
        )

        matching_settlements = settlement_map.get(transaction_id, [])

        # No settlement found
        if not matching_settlements:
            results.append({
                "transaction_id": transaction_id,
                "status": "exception",
                "exception_type": "missing_settlement",
                "expected_amount": expected_amount,
                "actual_amount": None,
            })
            continue

        # More than one settlement
        if len(matching_settlements) > 1:
            results.append({
                "transaction_id": transaction_id,
                "status": "exception",
                "exception_type": "duplicate_settlement",
                "expected_amount": expected_amount,
                "actual_amount": float(
                    matching_settlements[0]["settled_amount"]
                ),
            })
            continue

        settlement = matching_settlements[0]

        actual_amount = float(settlement["settled_amount"])

        settlement_date = date.fromisoformat(
            settlement["settlement_date"]
        )

        # Amount mismatch
        if abs(expected_amount - actual_amount) > 0.01:
            results.append({
                "transaction_id": transaction_id,
                "status": "exception",
                "exception_type": "amount_mismatch",
                "expected_amount": expected_amount,
                "actual_amount": actual_amount,
            })
            continue

        # Fee mismatch
        expected_fee = round(expected_amount * 0.02, 2)
        actual_fee = float(settlement.get("fee") or 0)

        if abs(expected_fee - actual_fee) > 0.01:
            results.append({
                "transaction_id": transaction_id,
                "status": "exception",
                "exception_type": "fee_mismatch",
                "expected_amount": expected_amount,
                "actual_amount": actual_amount,
            })
            continue

        # Settlement date too far from transaction date
        days_difference = (settlement_date - transaction_date).days

        if days_difference > 5:
            results.append({
                "transaction_id": transaction_id,
                "status": "exception",
                "exception_type": "date_mismatch",
                "expected_amount": expected_amount,
                "actual_amount": actual_amount,
            })
            continue

        # Everything matches
        results.append({
            "transaction_id": transaction_id,
            "status": "reconciled",
            "exception_type": None,
            "expected_amount": expected_amount,
            "actual_amount": actual_amount,
        })

    counts = Counter(
        result["status"] for result in results
    )

    exception_counts = Counter(
        result["exception_type"]
        for result in results
        if result["exception_type"]
    )

    summary = {
        "total_transactions": len(transactions),
        "reconciled": counts.get("reconciled", 0),
        "exceptions": counts.get("exception", 0),
        "exception_breakdown": dict(exception_counts),
    }

    return results, summary