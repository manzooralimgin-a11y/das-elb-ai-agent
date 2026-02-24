"""
Agent 3: Policy Validator
Validates extracted entities against hotel rules and calls live hotel APIs
to check real-time room availability and pricing.
"""
import json
import logging
import httpx
from app.agents.base_agent import call_claude
from app.knowledge.hotel_kb import HOTEL_KNOWLEDGE_BASE
from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""You are a hotel policy validator for Das ELB Hotel & Restaurant.

{HOTEL_KNOWLEDGE_BASE}

You are given extracted booking entities and real-time availability data from the hotel's live API.
Determine whether the request is fulfillable, calculate accurate pricing, identify policy issues,
suggest alternatives if needed, and flag upsell opportunities.

Return ONLY valid JSON:
{{
  "is_fulfillable": <true | false>,
  "availability_checked": <true | false>,
  "room_available": <true | false | null>,
  "live_price_per_night": <float or null>,
  "total_estimated_price": <float or null>,
  "price_breakdown": {{
    "room_nights": <float or null>,
    "conference_room": <float or null>,
    "catering": <float or null>,
    "equipment": <float or null>,
    "total": <float or null>
  }},
  "policy_issues": ["<issue description>"],
  "alternatives": [
    {{
      "room_type": "<alternative>",
      "price_per_night": <float>,
      "reason": "<why recommended>"
    }}
  ],
  "requires_manager_approval": <true | false>,
  "manager_approval_reason": "<string or null>",
  "upsell_opportunities": ["<natural upsell suggestion>"],
  "policy_notes": "<any policy to communicate to guest or null>"
}}

APPROVAL RULES:
- Group >10 guests → requires_manager_approval: true
- Estimated revenue >€5,000 → requires_manager_approval: true
- Cancellation dispute → requires_manager_approval: true"""


def _fetch_availability(room_type: str, check_in: str, check_out: str) -> dict:
    """Call the existing hotel management API for real-time availability."""
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(
                f"{settings.HOTEL_MGMT_API_BASE}/api/public/availability",
                params={
                    "check_in": check_in,
                    "check_out": check_out,
                    "room_type": room_type,
                },
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.warning(f"Availability API call failed: {e}")
    return {}


def _fetch_rooms() -> list:
    """Call the existing hotel management API for live room pricing."""
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{settings.HOTEL_MGMT_API_BASE}/api/public/rooms")
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.warning(f"Rooms API call failed: {e}")
    return []


def validate_policy(entities: dict, intent: str) -> dict:
    availability_data = {}
    rooms_data = []

    check_in = entities.get("check_in_date")
    check_out = entities.get("check_out_date")
    room_type = entities.get("room_type_requested")

    if check_in and room_type:
        availability_data = _fetch_availability(
            room_type, check_in, check_out or ""
        )

    if intent in ("room_booking", "group_booking"):
        rooms_data = _fetch_rooms()

    context = (
        f"INTENT: {intent}\n\n"
        f"EXTRACTED ENTITIES:\n{json.dumps(entities, indent=2)}\n\n"
        f"LIVE AVAILABILITY RESPONSE:\n{json.dumps(availability_data, indent=2)}\n\n"
        f"LIVE ROOMS DATA:\n{json.dumps(rooms_data, indent=2)}"
    )
    return call_claude(SYSTEM_PROMPT, context, max_tokens=1024)
