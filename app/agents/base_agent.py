"""Shared Gemini API call wrapper with JSON parsing and retry logic."""
import json
import logging
import re
import time

import google.generativeai as genai
import google.api_core.exceptions

from app.config import settings

logger = logging.getLogger(__name__)

# Configure Gemini once at module load
genai.configure(api_key=settings.GEMINI_API_KEY)

# Disable all safety filters — hotel emails are not harmful content
_SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

# Token budget progression for MAX_TOKENS retries
_TOKEN_STEPS = [512, 1024, 2048, 4096, 8192]


def call_claude(
    system_prompt: str,
    user_message: str,
    max_tokens: int = None,
    retries: int = 5,
) -> dict:
    """
    Call Gemini API and return parsed JSON response.
    Named call_claude for backward compatibility with all 5 agent files.

    Retry strategy:
    - MAX_TOKENS (finish_reason=2): step up token budget through _TOKEN_STEPS
    - ResourceExhausted (rate limit): exponential backoff
    - JSONDecodeError: sanitize and retry, then return empty dict on final failure
    - Other API errors: exponential backoff
    """
    base_tokens = max_tokens or settings.GEMINI_MAX_TOKENS

    # Build the token ladder starting at base_tokens
    token_ladder = [t for t in _TOKEN_STEPS if t >= base_tokens] or [base_tokens]
    token_idx = 0
    current_max = token_ladder[0]

    attempt = 0
    while attempt < retries:
        try:
            model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                system_instruction=system_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=settings.GEMINI_TEMPERATURE,
                    max_output_tokens=current_max,
                ),
                safety_settings=_SAFETY_SETTINGS,
            )

            response = model.generate_content(user_message)

            candidate = response.candidates[0] if response.candidates else None
            finish_reason = candidate.finish_reason if candidate else None

            if finish_reason == 2:
                # MAX_TOKENS — step up token budget
                token_idx += 1
                if token_idx < len(token_ladder):
                    current_max = token_ladder[token_idx]
                    logger.warning(
                        f"Gemini MAX_TOKENS on attempt {attempt + 1}, "
                        f"retrying with {current_max} tokens"
                    )
                    attempt += 1
                    time.sleep(0.5)
                    continue
                else:
                    # Already at 8192 — give up on MAX_TOKENS
                    logger.error("Gemini MAX_TOKENS even at 8192 tokens — giving up")
                    raise RuntimeError("Gemini MAX_TOKENS exceeded even at 8192 tokens")

            if finish_reason == 3:
                logger.error("Gemini SAFETY block — should not happen with hotel content")
                raise RuntimeError("Gemini safety filter triggered unexpectedly")

            # Extract text safely
            if candidate and candidate.content and candidate.content.parts:
                raw = candidate.content.parts[0].text.strip()
            else:
                raw = response.text.strip()

            return _parse_json(raw)

        except google.api_core.exceptions.ResourceExhausted:
            wait = min(2 ** attempt, 30)
            logger.warning(f"Gemini rate limit — waiting {wait}s (attempt {attempt + 1})")
            time.sleep(wait)
            attempt += 1

        except google.api_core.exceptions.GoogleAPICallError as e:
            logger.error(f"Gemini API error on attempt {attempt + 1}: {e}")
            if attempt >= retries - 1:
                raise
            time.sleep(2)
            attempt += 1

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error on attempt {attempt + 1}: {e} — sanitizing and retrying")
            if attempt >= retries - 1:
                # Last attempt: return empty dict so pipeline can handle gracefully
                logger.error("JSON parse failed on all attempts — returning empty dict")
                return {}
            time.sleep(1)
            attempt += 1

    raise RuntimeError("Gemini API call failed after all retries")


def _parse_json(raw: str) -> dict:
    """Strip markdown code fences, sanitize bad escapes, and parse JSON."""
    # Remove ```json ... ``` or ``` ... ``` wrappers
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Sanitize invalid escape sequences (e.g. \P, \B, \S that aren't valid JSON escapes)
        # Replace any backslash not followed by a valid JSON escape char with \\
        sanitized = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', cleaned)
        return json.loads(sanitized)
