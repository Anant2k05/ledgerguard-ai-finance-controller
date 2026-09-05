import os

from dotenv import load_dotenv
from supabase import create_client

from ai_investigator import investigate_exception


load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)


# Get the first unresolved exception
exception = (
    supabase
    .table("exceptions")
    .select("*")
    .eq("status", "unresolved")
    .limit(1)
    .execute()
    .data
)

if not exception:
    print("No unresolved exceptions found.")
    exit()

exception = exception[0]

transaction_id = exception["transaction_id"]

# Get the corresponding transaction
transaction = (
    supabase
    .table("transactions")
    .select("*")
    .eq("transaction_id", transaction_id)
    .limit(1)
    .execute()
    .data
)

if not transaction:
    print(f"Transaction {transaction_id} not found.")
    exit()

transaction = transaction[0]


# Get corresponding settlement(s)
settlement = (
    supabase
    .table("settlements")
    .select("*")
    .eq("transaction_id", transaction_id)
    .limit(1)
    .execute()
    .data
)

settlement = settlement[0] if settlement else None


print("\n=== INVESTIGATING EXCEPTION ===")
print(f"Transaction: {transaction_id}")
print(f"Exception: {exception['exception_type']}")


# Send data to Gemini
investigation = investigate_exception(
    exception,
    transaction,
    settlement
)


print("\n=== AI INVESTIGATION ===")
print(investigation)


# Store AI investigation
investigation_row = {
    "exception_id": exception["id"],
    "root_cause": investigation["root_cause"],
    "evidence": investigation["evidence"],
    "recommended_action": investigation["recommended_action"],
    "confidence": investigation["confidence"],
    "requires_human_review": investigation["requires_human_review"]
}

supabase.table("ai_investigations").insert(
    investigation_row
).execute()


# Create audit log
audit_row = {
    "exception_id": exception["id"],
    "action": "ai_investigation",
    "actor": "LedgerGuard AI",
    "details": "AI investigation generated and stored."
}

supabase.table("audit_logs").insert(
    audit_row
).execute()


print("\nInvestigation saved to Supabase.")
print("Audit log created.")