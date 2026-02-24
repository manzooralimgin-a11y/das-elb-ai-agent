"""
Agent 5: Risk & Sentiment Analyzer
Detects anger, legal risk, VIP signals, complaint severity, and revenue potential.
Runs in parallel with Agents 1 & 2.
"""
from app.agents.base_agent import call_claude

SYSTEM_PROMPT = """You are a risk and sentiment analysis specialist for a hotel email management system.

Analyze the incoming email for:
1. Emotional tone and anger level
2. Legal risk indicators (threats, consumer protection complaints, review threats)
3. VIP or high-value signals
4. Complaint severity
5. Revenue potential
6. Whether this is an automated/system message that needs no reply

Return ONLY valid JSON with no markdown or explanation:
{
  "sentiment": "very_negative" | "negative" | "neutral" | "positive" | "very_positive",
  "anger_level": <0 to 10>,
  "legal_risk": <true | false>,
  "legal_risk_indicators": ["<specific phrase or signal>"],
  "is_vip_signal": <true | false>,
  "vip_indicators": ["<what signals VIP status>"],
  "complaint_severity": "none" | "low" | "medium" | "high" | "critical",
  "requires_manager_escalation": <true | false>,
  "escalation_reason": "<string or null>",
  "estimated_revenue_eur": <float or null>,
  "revenue_category": "low" | "medium" | "high" | "vip",
  "notify_staff_immediately": <true | false>,
  "notification_reason": "<string or null>",
  "overall_risk_score": <0.0 to 1.0>,
  "recommended_priority": "low" | "normal" | "high" | "urgent",
  "is_automated_message": <true | false>,
  "automated_message_reason": "<why this is automated/no-reply-needed, or null>"
}

AUTOMATED MESSAGE RULES — set is_automated_message: true if:
- Subject starts with "Automatische Antwort", "Auto-reply", "Out of office", "Abwesenheit"
- Subject or body contains "Newsletter", "Unsubscribe", "Abmelden"
- From a booking platform (booking.com, expedia, hotels.com, airbnb, trivago)
- Contains "noreply@", "no-reply@", "donotreply@" in From header
- Is a payment confirmation, invoice, or system notification
- Contains "Buchungsbestätigung", "Ihre Reservierung", "Zahlungseingang"
- Is a bounce/delivery failure notification

ESCALATION RULES:
- complaint_severity high or critical → requires_manager_escalation: true
- legal_risk: true → requires_manager_escalation: true
- estimated_revenue_eur > 5000 → notify_staff_immediately: true
- anger_level >= 8 → recommended_priority: urgent"""


def analyze_risk(
    email_subject: str,
    email_body: str,
    intent: str,
    estimated_revenue: float = None,
) -> dict:
    user_message = (
        f"Intent: {intent}\n"
        f"Estimated revenue from entities: {estimated_revenue}\n\n"
        f"Subject: {email_subject}\n\n"
        f"Body:\n{email_body}"
    )
    return call_claude(SYSTEM_PROMPT, user_message, max_tokens=768)
