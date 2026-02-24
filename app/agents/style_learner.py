"""
Style Learner Agent
Analyzes a batch of sent emails from Das ELB staff to extract:
- Writing patterns, tone, greeting/sign-off style
- Which email types don't need a reply (newsletters, automated, OTA confirmations)
- Per-intent example replies for use as few-shot examples
- A formatted prompt injection for Agent 4 (Response Writer)
"""
import json
import logging
from typing import List
from app.agents.base_agent import call_claude

logger = logging.getLogger(__name__)

STYLE_LEARNER_SYSTEM_PROMPT = """You are analyzing a collection of emails sent by Das ELB Hotel & Restaurant staff.
Your goal is to deeply understand their exact writing style so an AI agent can replicate it perfectly.

Analyze ALL provided emails and extract:

1. GREETING PATTERNS — How do they address guests? (e.g., "Sehr geehrter Herr X", "Guten Tag Frau X", "Liebes Team")
2. SIGN-OFF STYLE — The exact closing block used (name, title, contact info format)
3. TONE MARKERS — Characteristic words/phrases they always use (e.g., "gerne", "herzlich", "selbstverständlich")
4. STRUCTURAL HABITS — Do they use bullet points? Numbered lists? Short paragraphs?
5. AVERAGE LENGTH — Approximate word count of their replies
6. ALWAYS INCLUDES — Things they never forget (check-in time, contact block, specific disclaimer)
7. NEVER DOES — Patterns they avoid (informal language, certain phrases)
8. NO-REPLY INDICATORS — Patterns in subjects/bodies of emails they DO NOT reply to (automated, newsletters, OTA booking confirmations, internal CC chains)
9. PER-INTENT EXAMPLES — For each intent type, find the best example body text

Return ONLY valid JSON (no markdown):
{
  "greeting_patterns": ["<pattern 1>", "<pattern 2>"],
  "sign_off": "<exact full sign-off block including name, title, hotel contact>",
  "tone_words": ["<word/phrase 1>", "<word/phrase 2>"],
  "structural_style": "<description of how they format replies>",
  "avg_length_words": <integer>,
  "always_includes": ["<item 1>", "<item 2>"],
  "never_does": ["<item 1>", "<item 2>"],
  "no_reply_indicators": ["<subject pattern 1>", "<subject pattern 2>"],
  "no_reply_sender_patterns": ["<domain/keyword that means no-reply needed>"],
  "per_intent_samples": {
    "conference_inquiry": "<best example reply body, or null if not found>",
    "room_booking": "<best example reply body, or null if not found>",
    "complaint": "<best example reply body, or null if not found>",
    "general_inquiry": "<best example reply body, or null if not found>"
  },
  "key_insights": "<2-3 sentence summary of what makes this hotel's writing style distinctive>"
}"""


def analyze_sent_emails(sent_emails: List[dict]) -> dict:
    """
    Feed sent emails to Gemini to extract the hotel's writing style.
    Returns the raw profile dict extracted by the AI.
    """
    if not sent_emails:
        logger.warning("No sent emails provided for style analysis")
        return _default_profile()

    # Build the user message with all sent email bodies
    email_texts = []
    for i, e in enumerate(sent_emails[:40], 1):  # cap at 40 to manage token budget
        email_texts.append(
            f"--- EMAIL {i} ---\n"
            f"Subject: {e.get('subject', '')}\n"
            f"To: {e.get('to_email', '')}\n"
            f"Body:\n{e.get('body', '')[:800]}\n"  # cap each at 800 chars
        )

    user_message = (
        f"Here are {len(sent_emails)} emails sent by Das ELB Hotel staff.\n"
        f"Analyze them and extract the writing style profile.\n\n"
        + "\n".join(email_texts)
    )

    try:
        result = call_claude(STYLE_LEARNER_SYSTEM_PROMPT, user_message, max_tokens=4096)
        if not result or not isinstance(result, dict):
            logger.error("Style learner returned invalid result")
            return _default_profile()
        logger.info(f"Style analysis complete — {len(sent_emails)} emails analyzed")
        return result
    except Exception as e:
        logger.error(f"Style learning failed: {e}", exc_info=True)
        return _default_profile()


def build_style_injection(profile: dict) -> str:
    """
    Convert the extracted style profile into a formatted prompt section
    that gets injected into Agent 4 (Response Writer) system prompt.
    """
    lines = ["## LEARNED WRITING STYLE (from actual hotel email history)\n"]

    if profile.get("sign_off"):
        lines.append(f"EXACT SIGN-OFF TO USE:\n{profile['sign_off']}\n")

    if profile.get("greeting_patterns"):
        lines.append("GREETING PATTERNS USED BY STAFF:")
        for p in profile["greeting_patterns"][:4]:
            lines.append(f"  - {p}")
        lines.append("")

    if profile.get("tone_words"):
        lines.append(f"CHARACTERISTIC TONE WORDS: {', '.join(profile['tone_words'][:10])}")

    if profile.get("structural_style"):
        lines.append(f"STRUCTURAL STYLE: {profile['structural_style']}")

    if profile.get("avg_length_words"):
        lines.append(f"TARGET LENGTH: approximately {profile['avg_length_words']} words")

    if profile.get("always_includes"):
        lines.append("\nALWAYS INCLUDE:")
        for item in profile["always_includes"][:5]:
            lines.append(f"  - {item}")

    if profile.get("never_does"):
        lines.append("\nNEVER DO:")
        for item in profile["never_does"][:5]:
            lines.append(f"  - {item}")

    # Add per-intent few-shot examples (only if available and not too long)
    samples = profile.get("per_intent_samples", {})
    for intent, sample in samples.items():
        if sample and len(sample) > 50:
            lines.append(f"\nEXAMPLE {intent.upper().replace('_',' ')} REPLY:")
            lines.append(sample[:600])  # cap at 600 chars per example

    if profile.get("key_insights"):
        lines.append(f"\nSTYLE INSIGHT: {profile['key_insights']}")

    return "\n".join(lines)


def _default_profile() -> dict:
    """Fallback when no sent emails are available yet."""
    return {
        "greeting_patterns": ["Sehr geehrter Herr/Frau X", "Guten Tag,"],
        "sign_off": "Mit freundlichen Grüßen,\nDas Team vom Das ELB Hotel & Restaurant\nSeilerweg 19, 39114 Magdeburg\n+49 391 756 326 60 | info@das-elb.de",
        "tone_words": ["gerne", "herzlich willkommen", "freuen uns", "selbstverständlich"],
        "structural_style": "Short paragraphs, professional German formal style",
        "avg_length_words": 120,
        "always_includes": ["check-in time 13:00", "check-out time 11:00", "contact block"],
        "never_does": ["uses informal 'du'", "invents prices"],
        "no_reply_indicators": ["Automatische Antwort", "Newsletter", "Buchungsbestätigung", "Unzustellbar", "Abwesenheitsnotiz"],
        "no_reply_sender_patterns": ["noreply", "no-reply", "donotreply", "booking.com", "expedia", "hotels.com"],
        "per_intent_samples": {},
        "key_insights": "Professional German hotel tone with formal Sie form, warm but concise replies.",
    }
