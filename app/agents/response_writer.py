"""
Agent 4: Response Writer
Generates a professional, bilingual (DE/EN) email reply using all previous agent outputs.
"""
import json
from app.agents.base_agent import call_claude
from app.knowledge.hotel_kb import HOTEL_KNOWLEDGE_BASE

SYSTEM_PROMPT = f"""You are the professional guest relations email writer for Das ELB Hotel & Restaurant in Magdeburg, Germany.

{HOTEL_KNOWLEDGE_BASE}

STRICT WRITING RULES:
1. Match the guest's language exactly (DE or EN). If uncertain, write German with a brief English note.
2. German: Use formal "Sie" form (never "du"). Warm but professional tone.
3. English: Professional and welcoming tone.
4. Always use exact prices from the knowledge base or live API data — never invent pricing.
5. For bookings: always state check-in time (13:00) and check-out time (11:00).
6. For unavailable rooms: apologize genuinely, offer real alternatives with their prices.
7. For complaints with anger_level >= 6: lead with sincere empathy, offer concrete resolution, do NOT be defensive.
8. Naturally weave in the most relevant upsell opportunity from Agent 3 if appropriate — never pushy.
9. Maximum length: 350 words for standard replies, 500 words for conference quotes.
10. Always end with the hotel contact block.

GERMAN SIGN-OFF:
Mit freundlichen Grüßen,
Das Team vom Das ELB Hotel & Restaurant
Seilerweg 19, 39114 Magdeburg
+49 391 756 326 60 | rezeption@das-elb.de | www.das-elb-hotel.com

ENGLISH SIGN-OFF:
Warm regards,
The Das ELB Team
Seilerweg 19, 39114 Magdeburg, Germany
+49 391 756 326 60 | rezeption@das-elb.de | www.das-elb-hotel.com

Return ONLY valid JSON (no markdown):
{{
  "subject": "<reply subject line — Re: original subject>",
  "body_text": "<full plain-text email body with correct line breaks>",
  "detected_language": "de" | "en",
  "includes_price_quote": <true | false>,
  "includes_booking_confirmation": <true | false>,
  "action_required_by_staff": "<any action staff must take before sending, or null>"
}}"""


def write_response(
    email_subject: str,
    email_body: str,
    intent: str,
    entities: dict,
    policy: dict,
    risk: dict,
    language: str,
    vip_info: dict = None,
    style_injection: str = "",
    similar_past_emails: list = None,
) -> dict:
    # Build the full system prompt — inject the learned style profile if available
    if style_injection:
        full_system_prompt = SYSTEM_PROMPT + "\n\n" + style_injection
    else:
        full_system_prompt = SYSTEM_PROMPT

    rag_text = ""
    if similar_past_emails:
        rag_text = "\n\nPAST HUMAN REPLIES TO HIGHLY SIMILAR EMAILS (Use these as absolute primary templates for phrasing, tone, and formatting):\n"
        for i, ref in enumerate(similar_past_emails, 1):
            score = ref.get('similarity_score', 0)
            rag_text += f"-- Reference {i} (Relevance: {score:.2f}) --\n"
            rag_text += f"Human Subject: {ref.get('subject', '')}\n"
            rag_text += f"Human Body:\n{ref.get('body', '')}\n\n"

    context = (
        f"ORIGINAL EMAIL:\n"
        f"Subject: {email_subject}\n"
        f"Body:\n{email_body}\n\n"
        f"INTENT: {intent}\n"
        f"DETECTED LANGUAGE: {language}\n\n"
        f"EXTRACTED ENTITIES:\n{json.dumps(entities, indent=2)}\n\n"
        f"POLICY VALIDATION:\n{json.dumps(policy, indent=2)}\n\n"
        f"RISK ASSESSMENT:\n{json.dumps(risk, indent=2)}\n\n"
        f"VIP STATUS: {json.dumps(vip_info) if vip_info else 'Not a known VIP guest'}\n"
        f"{rag_text}"
    )
    return call_claude(full_system_prompt, context, max_tokens=2048)

def refine_draft(
    original_subject: str,
    original_body: str,
    current_draft_subject: str,
    current_draft_body: str,
    instructions: str,
    language: str,
) -> dict:
    REFINE_SYSTEM_PROMPT = f"""You are the professional guest relations email writer for Das ELB Hotel & Restaurant in Magdeburg, Germany.

{HOTEL_KNOWLEDGE_BASE}

The user (a hotel staff member) has instructed you to modify an existing email draft.
You must strictly follow their instruction while maintaining the exact same language format and professional tone of the existing draft.

Return ONLY valid JSON (no markdown):
{{
  "subject": "<updated subject line>",
  "body_text": "<full plain-text email body with correct line breaks>"
}}"""

    context = (
        f"ORIGINAL EMAIL RECEIVED FROM GUEST:\n"
        f"Subject: {original_subject}\n"
        f"Body:\n{original_body}\n\n"
        f"CURRENT AI DRAFT REPLY:\n"
        f"Subject: {current_draft_subject}\n"
        f"Body:\n{current_draft_body}\n\n"
        f"STAFF INSTRUCTION TO REFINE DRAFT:\n"
        f"{instructions}\n\n"
        f"LANGUAGE DETECTED: {language}\n\n"
        f"Apply the staff instruction to the draft. Keep everything else intact. Adhere to hotel policies from the knowledge base."
    )
    
    return call_claude(REFINE_SYSTEM_PROMPT, context, max_tokens=2048)
