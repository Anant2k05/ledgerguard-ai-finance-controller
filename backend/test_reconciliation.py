import os

from dotenv import load_dotenv
from supabase import create_client

from reconciliation import reconcile_transactions


load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

transactions = (
    supabase
    .table("transactions")
    .select("*")
    .execute()
    .data
)

settlements = (
    supabase
    .table("settlements")
    .select("*")
    .execute()
    .data
)

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