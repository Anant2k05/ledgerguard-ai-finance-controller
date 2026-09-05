import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from supabase import create_client, Client
from reconciliation import reconcile_transactions
from ai_investigator import investigate_exception

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase environment variables are missing")

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

app = FastAPI(title="LedgerGuard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "LedgerGuard API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.get("/dashboard")
def dashboard():

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

    exceptions = (
        supabase
        .table("exceptions")
        .select("*")
        .execute()
        .data
    )

    investigations = (
        supabase
        .table("ai_investigations")
        .select("*")
        .execute()
        .data
    )

    total_transactions = len(transactions)
    total_exceptions = len(exceptions)
    reconciled = total_transactions - total_exceptions

    reconciliation_rate = (
        round((reconciled / total_transactions) * 100, 2)
        if total_transactions
        else 0
    )

    expected_volume = round(
        sum(float(t["amount"]) for t in transactions), 2
    )

    settled_volume = round(
        sum(float(s["settled_amount"]) for s in settlements), 2
    )

    discrepancy_float = round(expected_volume - settled_volume, 2)

    exception_breakdown = {}

    for exception in exceptions:
        exception_type = exception.get("exception_type") or "unknown"
        exception_breakdown[exception_type] = (
            exception_breakdown.get(exception_type, 0) + 1
        )

    return {
        "total_transactions": total_transactions,
        "total_exceptions": total_exceptions,
        "total_ai_investigations": len(investigations),
        "reconciled": reconciled,
        "exceptions": total_exceptions,
        "reconciliation_rate": reconciliation_rate,
        "expected_volume": expected_volume,
        "settled_volume": settled_volume,
        "discrepancy_float": discrepancy_float,
        "exception_breakdown": exception_breakdown,
    }


@app.get("/transactions")
def get_transactions():

    result = (
        supabase
        .table("transactions")
        .select("*")
        .order("transaction_date", desc=True)
        .execute()
    )

    return result.data


@app.get("/exceptions")
def get_exceptions():

    result = (
        supabase
        .table("exceptions")
        .select("*")
        .order("detected_at", desc=True)
        .execute()
    )

    return result.data


@app.get("/investigations")
def get_investigations():

    result = (
        supabase
        .table("ai_investigations")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )

    return result.data


@app.post("/reconcile")
def run_reconciliation():
    transactions = (
        supabase.table("transactions")
        .select("*")
        .execute()
        .data
    )

    settlements = (
        supabase.table("settlements")
        .select("*")
        .execute()
        .data
    )

    merchants_by_transaction = {
        transaction["transaction_id"]: transaction.get("merchant")
        for transaction in transactions
    }

    results, summary = reconcile_transactions(
        transactions,
        settlements
    )

    # Clear previous reconciliation results
    supabase.table("audit_logs").delete().neq("id", 0).execute()
    supabase.table("ai_investigations").delete().neq("id", 0).execute()
    supabase.table("exceptions").delete().neq("id", 0).execute()

    # Store fresh exceptions
    exception_rows = []

    for result in results:
        if result["status"] == "exception":
            exception_rows.append({
                "transaction_id": result["transaction_id"],
                "merchant": merchants_by_transaction.get(
                    result["transaction_id"]
                ),
                "exception_type": result["exception_type"],
                "expected_amount": result["expected_amount"],
                "actual_amount": result["actual_amount"],
                "status": "unresolved"
            })

    if exception_rows:
        supabase.table("exceptions").insert(
            exception_rows
        ).execute()

    return {
        "message": "Reconciliation completed successfully",
        "summary": summary
    }


@app.post("/exceptions/{exception_id}/investigate")
def investigate_exception_api(exception_id: int):

    # Get exception
    exception_result = (
        supabase.table("exceptions")
        .select("*")
        .eq("id", exception_id)
        .limit(1)
        .execute()
    )

    if not exception_result.data:
        return {"error": "Exception not found"}

    exception = exception_result.data[0]
    transaction_id = exception["transaction_id"]

    # Get transaction
    transaction_result = (
        supabase.table("transactions")
        .select("*")
        .eq("transaction_id", transaction_id)
        .limit(1)
        .execute()
    )

    if not transaction_result.data:
        return {"error": "Transaction not found"}

    transaction = transaction_result.data[0]

    # Get settlement if one exists
    settlement_result = (
        supabase.table("settlements")
        .select("*")
        .eq("transaction_id", transaction_id)
        .limit(1)
        .execute()
    )

    settlement = (
        settlement_result.data[0]
        if settlement_result.data
        else None
    )

    # Ask Gemini to investigate
    try:
        investigation = investigate_exception(
            exception,
            transaction,
            settlement
        )

        investigation_row = {
            "exception_id": exception_id,
            "root_cause": investigation["root_cause"],
            "evidence": investigation["evidence"],
            "recommended_action": investigation["recommended_action"],
            "confidence": investigation["confidence"],
            "requires_human_review": investigation["requires_human_review"]
        }
    except Exception as ai_error:
        # Any Gemini failure (outage, timeout, auth, rate limit, malformed
        # JSON, missing fields, etc.) lands here. No investigation record is
        # written and the exception's status is left untouched, so it stays
        # unresolved and visible for human review.
        failure_reason = f"{type(ai_error).__name__}: {ai_error}"[:300]

        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            failure_reason = failure_reason.replace(gemini_key, "[REDACTED]")

        supabase.table("audit_logs").insert({
            "exception_id": exception_id,
            "action": "ai_investigation_failed",
            "actor": "LedgerGuard AI",
            "details": (
                f"AI investigation failed for exception {exception_id}: "
                f"{failure_reason}"
            )
        }).execute()

        return JSONResponse(
            status_code=503,
            content={
                "error": "AI investigation unavailable",
                "message": "Gemini investigation failed. Human review is required."
            }
        )

    # Save AI investigation
    saved_investigation = (
        supabase.table("ai_investigations")
        .insert(investigation_row)
        .execute()
    )

    # Create audit log
    audit_row = {
        "exception_id": exception_id,
        "action": "ai_investigation",
        "actor": "LedgerGuard AI",
        "details": "AI investigation generated and stored."
    }

    supabase.table("audit_logs").insert(audit_row).execute()

    return {
        "message": "AI investigation completed",
        "investigation": investigation
    }

@app.post("/exceptions/{exception_id}/approve")
def approve_exception(exception_id: int):

    result = (
        supabase.table("exceptions")
        .update({"status": "resolved"})
        .eq("id", exception_id)
        .execute()
    )

    if not result.data:
        return {"error": "Exception not found"}

    supabase.table("audit_logs").insert({
        "exception_id": exception_id,
        "action": "approved",
        "actor": "human_reviewer",
        "details": "Exception reviewed and approved."
    }).execute()

    return {
        "message": "Exception approved",
        "exception_id": exception_id,
        "status": "resolved"
    }


@app.post("/exceptions/{exception_id}/reject")
def reject_exception(exception_id: int):

    result = (
        supabase.table("exceptions")
        .update({"status": "rejected"})
        .eq("id", exception_id)
        .execute()
    )

    if not result.data:
        return {"error": "Exception not found"}

    supabase.table("audit_logs").insert({
        "exception_id": exception_id,
        "action": "rejected",
        "actor": "human_reviewer",
        "details": "Exception reviewed and rejected."
    }).execute()

    return {
        "message": "Exception rejected",
        "exception_id": exception_id,
        "status": "rejected"
    }

@app.get("/audit-logs")
def get_audit_logs():
    result = (
        supabase.table("audit_logs")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )

    return result.data or []
    