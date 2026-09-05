import os
import json

from dotenv import load_dotenv
from google import genai


load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


def investigate_exception(exception, transaction, settlement=None):

    prompt = f"""
You are LedgerGuard, an AI Finance Controller.

Investigate this financial reconciliation exception.

Transaction:
{json.dumps(transaction, indent=2)}

Settlement:
{json.dumps(settlement, indent=2) if settlement else "No settlement found"}

Exception:
{json.dumps(exception, indent=2)}

Your job is to explain the exception using ONLY the supplied data.

Return ONLY valid JSON with exactly these fields:

{{
    "root_cause": "short explanation",
    "evidence": "specific evidence from the records",
    "recommended_action": "practical corrective action",
    "confidence": 0.0,
    "requires_human_review": true
}}

Rules:
- Do not invent missing information.
- confidence must be between 0 and 1.
- Financial actions must require human review.
- If evidence is insufficient, say so.
"""

    interaction = client.interactions.create(
        model="gemini-3.6-flash",
        input=prompt
    )

    text = interaction.output_text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

    return json.loads(text)