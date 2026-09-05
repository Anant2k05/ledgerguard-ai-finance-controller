import os

from dotenv import load_dotenv
from supabase import create_client

from reconciliation import reconcile_transactions


load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)


# Fetch transactions
transactions = (
    supabase
    .table("transactions")
    .select("*")
    .execute()
    .data
)


# Fetch settlements
settlements = (
    supabase
    .table("settlements")
    .select("*")
    .execute()
    .data
)


# Run reconciliation
results, summary = reconcile_transactions(
    transactions,
    settlements
)


print("\n=== LEDGERGUARD RECONCILIATION ===")

print(f"Total transactions: {summary['total_transactions']}")
print(f"Reconciled: {summary['reconciled']}")
print(f"Exceptions: {summary['exceptions']}")

print("\nException breakdown:")

for exception_type, count in summary["exception_breakdown"].items():
    print(f"  {exception_type}: {count}")


# Store exceptions in Supabase
exception_rows = []

for result in results:

    if result["status"] == "exception":

        exception_rows.append({
            "transaction_id": result["transaction_id"],
            "exception_type": result["exception_type"],
            "expected_amount": result["expected_amount"],
            "actual_amount": result["actual_amount"],
            "status": "unresolved"
        })


if exception_rows:

    supabase.table("exceptions").insert(
        exception_rows
    ).execute()

    print(
        f"\nInserted {len(exception_rows)} exceptions into Supabase."
    )

else:

    print("\nNo exceptions found.")