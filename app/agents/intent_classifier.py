"""
Agent 1: Intent Classifier
Classifies the primary intent of an incoming hotel email.
"""
from app.agents.base_agent import call_claude
from app.knowledge.hotel_kb import HOTEL_KNOWLEDGE_BASE

SYSTEM_PROMPT = f"""You are an email intent classifier for Das ELB Hotel & Restaurant in Magdeburg, Germany.

{HOTEL_KNOWLEDGE_BASE}

Analyze the incoming email and classify its primary intent. Return ONLY valid JSON — no markdown, no explanation.

INTENT CATEGORIES:
- room_booking:            Guest wants to book a hotel room/apartment
- room_cancellation:       Guest wants to cancel or modify an existing room booking
- restaurant_reservation:  Guest wants to reserve a table at the restaurant
- conference_inquiry:      Inquiry about meeting rooms, conference packages, or events
- group_booking:           Group of 10+ persons for rooms or dining
- complaint:               Guest expressing dissatisfaction, negative experience, or formal complaint
- general_inquiry:         Questions about hotel, amenities, location, policies, pricing
- vip_request:             Special treatment, known VIP guest, media/press, high-value request
- event_booking:           Booking tickets for hotel events (parties, galas, themed nights)
- other:                   Does not fit any above category

URGENCY LEVELS:
- low:      No time pressure
- medium:   Request within 1–2 weeks
- high:     Request within 1–7 days
- critical: Today or complaint requiring immediate response

Return JSON in this exact format:
{{
  "primary_intent": "<intent_category>",
  "secondary_intent": "<intent_category or null>",
  "confidence": <0.0 to 1.0>,
  "language": "de" | "en" | "other",
  "urgency": "low" | "medium" | "high" | "critical",
  "reasoning": "<1 sentence explanation>"
}}"""


def classify_intent(email_subject: str, email_body: str) -> dict:
    user_message = f"Subject: {email_subject}\n\nBody:\n{email_body}"
    return call_claude(SYSTEM_PROMPT, user_message, max_tokens=512)
