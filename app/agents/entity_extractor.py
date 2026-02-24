"""
Agent 2: Entity Extractor
Extracts structured booking and contact data from an email.
"""
import json
from app.agents.base_agent import call_claude
from app.knowledge.hotel_kb import HOTEL_KNOWLEDGE_BASE

SYSTEM_PROMPT = f"""You are an entity extraction specialist for Das ELB Hotel & Restaurant in Magdeburg, Germany.

{HOTEL_KNOWLEDGE_BASE}

Extract all relevant structured information from the email. For any field not mentioned in the email, use null.
Dates must be in YYYY-MM-DD format. Times in HH:MM (24h). Return ONLY valid JSON.

OUTPUT FORMAT:
{{
  "guest_name": "<full name or null>",
  "guest_email": "<email address or null>",
  "guest_phone": "<phone number or null>",
  "company_name": "<company or null>",
  "check_in_date": "<YYYY-MM-DD or null>",
  "check_out_date": "<YYYY-MM-DD or null>",
  "nights": <integer or null>,
  "room_type_requested": "komfort" | "komfort plus" | "suite" | null,
  "num_adults": <integer or null>,
  "num_children": <integer or null>,
  "num_attendees": <integer or null>,
  "conference_room_preference": "veranstaltungsraum" | "workshop-405" | null,
  "catering_package": "starter" | "starter-plus" | "komfort" | null,
  "equipment_needed": [],
  "special_requests": "<string or null>",
  "budget_mentioned": "<string or null>",
  "estimated_revenue": <float or null>,
  "reservation_date": "<YYYY-MM-DD for restaurant or null>",
  "reservation_time": "<HH:MM or null>",
  "num_persons_dining": <integer or null>,
  "existing_booking_reference": "<reference number or null>",
  "field_confidence": {{
    "check_in_date": <0.0 to 1.0>,
    "check_out_date": <0.0 to 1.0>,
    "room_type_requested": <0.0 to 1.0>,
    "num_adults": <0.0 to 1.0>
  }}
}}

For estimated_revenue: calculate based on mentioned dates, room type, and guest count using prices from the knowledge base."""


def extract_entities(email_subject: str, email_body: str, intent: str) -> dict:
    user_message = (
        f"Classified intent: {intent}\n\n"
        f"Subject: {email_subject}\n\n"
        f"Body:\n{email_body}"
    )
    return call_claude(SYSTEM_PROMPT, user_message, max_tokens=1024)
