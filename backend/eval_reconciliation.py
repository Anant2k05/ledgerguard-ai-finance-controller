"""
Independent, read-only evaluation of reconciliation.reconcile_transactions()
against the synthetic scenarios defined in generate_data.py.

This script does NOT import or execute generate_data.py, and does NOT touch
Supabase, Gemini, or the network. It reproduces the exact same deterministic
generation logic (same random.seed, same merchant list, same per-iteration
random-call order, same scenario weights, same 150-transaction count)
entirely in memory. The ground-truth label for each transaction is recorded
directly from the scenario chosen during generation, BEFORE
reconcile_transactions() is ever invoked on the resulting data — so the
labels do not depend on, and are not derived from, the engine under test.
"""

import random
from datetime import date, timedelta
from collections import Counter

from reconciliation import reconcile_transactions


# ---------------------------------------------------------------------------
# 1. Reproduce the synthetic dataset (mirrors generate_data.py exactly)
# ---------------------------------------------------------------------------

random.seed(42)

MERCHANTS = [
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

START_DATE = date(2026, 8, 1)

SCENARIO_TO_LABEL = {
    "exact_match": "reconciled",
    "amount_mismatch": "amount_mismatch",
    "missing_settlement": "missing_settlement",
    "date_mismatch": "date_mismatch",
    "duplicate": "duplicate_settlement",
    "fee_mismatch": "fee_mismatch",
}

transactions = []
settlements = []
expected_labels = {}  # transaction_id -> ground-truth label, from the generator's intent

for i in range(1, 151):

    transaction_id = f"TXN-{i:04d}"
    transaction_date = START_DATE + timedelta(days=random.randint(0, 30))
    amount = round(random.uniform(200, 15000), 2)

    transactions.append({
        "transaction_id": transaction_id,
        "transaction_date": transaction_date.isoformat(),
        "merchant": random.choice(MERCHANTS),
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

    # Ground truth is fixed here, from the scenario itself, before
    # reconcile_transactions() ever sees this transaction.
    expected_labels[transaction_id] = SCENARIO_TO_LABEL[scenario]

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


# ---------------------------------------------------------------------------
# 2. Run the existing, unmodified reconciliation engine
# ---------------------------------------------------------------------------

results, _summary = reconcile_transactions(transactions, settlements)

predicted_labels = {
    result["transaction_id"]: (result["exception_type"] or "reconciled")
    for result in results
}


# ---------------------------------------------------------------------------
# 3. Score predictions against the independently generated ground truth
# ---------------------------------------------------------------------------

LABELS = [
    "reconciled",
    "amount_mismatch",
    "missing_settlement",
    "date_mismatch",
    "duplicate_settlement",
    "fee_mismatch",
]

total = len(transactions)
correct = 0
mismatches = []  # (transaction_id, expected, predicted)

confusion = {actual: Counter() for actual in LABELS}
ground_truth_distribution = Counter()

for transaction_id, expected in expected_labels.items():
    predicted = predicted_labels.get(transaction_id, "NO_RESULT")
    ground_truth_distribution[expected] += 1
    confusion[expected][predicted] += 1

    if predicted == expected:
        correct += 1
    else:
        mismatches.append((transaction_id, expected, predicted))

incorrect = total - correct
accuracy = correct / total if total else 0.0


def precision_recall(label):
    true_positive = confusion[label][label]
    false_negative = sum(
        confusion[label][other] for other in LABELS if other != label
    )
    false_positive = sum(
        confusion[actual][label] for actual in LABELS if actual != label
    )

    precision = (
        true_positive / (true_positive + false_positive)
        if (true_positive + false_positive) > 0
        else None
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if (true_positive + false_negative) > 0
        else None
    )
    return precision, recall


# ---------------------------------------------------------------------------
# 4. Report
# ---------------------------------------------------------------------------

def fmt_pct(value):
    return f"{value * 100:.2f}%" if value is not None else "n/a"


print("=" * 72)
print("LEDGERGUARD RECONCILIATION ENGINE - INDEPENDENT EVALUATION")
print("=" * 72)
print()
print(
    "Evaluation uses deterministic synthetic scenarios with independently\n"
    "assigned ground-truth labels. It validates implementation correctness\n"
    "against the generated scenarios; it does not validate real-world\n"
    "business thresholds."
)
print()

print("-" * 72)
print("DATASET")
print("-" * 72)
print(f"Total transactions evaluated : {total}")
print()

print("Ground-truth class distribution:")
for label in LABELS:
    count = ground_truth_distribution.get(label, 0)
    share = count / total if total else 0
    print(f"  {label:<22}{count:>5}   ({fmt_pct(share)})")
print()

print("-" * 72)
print("OVERALL RESULTS")
print("-" * 72)
print(f"Correctly classified    : {correct}")
print(f"Incorrectly classified  : {incorrect}")
print(f"Classification accuracy : {fmt_pct(accuracy)}")
print()

print("-" * 72)
print("PER-CLASS PRECISION / RECALL")
print("-" * 72)
print(f"{'label':<22}{'precision':>12}{'recall':>12}")
for label in LABELS:
    precision, recall = precision_recall(label)
    print(f"{label:<22}{fmt_pct(precision):>12}{fmt_pct(recall):>12}")
print()

print("-" * 72)
print("CONFUSION MATRIX (rows = ground truth, columns = predicted)")
print("-" * 72)
col_width = 12
header = "actual \\ predicted"
print(f"{header:<22}" + "".join(f"{label[:10]:>{col_width}}" for label in LABELS))
for actual in LABELS:
    row = confusion[actual]
    print(
        f"{actual:<22}"
        + "".join(f"{row.get(pred, 0):>{col_width}}" for pred in LABELS)
    )
print()

print("-" * 72)
print("MISMATCHED TRANSACTIONS")
print("-" * 72)
if mismatches:
    for transaction_id, expected, predicted in mismatches:
        print(f"  {transaction_id}: expected={expected}  predicted={predicted}")
else:
    print("  None - all transactions classified correctly.")
print()

print("=" * 72)
