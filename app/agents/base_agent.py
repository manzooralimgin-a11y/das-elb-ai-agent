"""Shared OpenAI API call wrapper with JSON parsing and retry logic."""
import json
import logging
import re
import time

from openai import OpenAI, RateLimitError, APIError

from app.config import settings

logger = logging.getLogger(__name__)

# Initialise OpenAI client once at module load
_client = OpenAI(api_key=settings.OPENAI_API_KEY)


def call_claude(
    system_prompt: str,
    user_message: str,
    max_tokens: int = None,
    retries: int = 5,
) -> dict:
    """
    Call OpenAI chat completions and return parsed JSON response.
    Named call_claude for backward compatibility with all agent files.

    Retry strategy:
    - RateLimitError (429): exponential backoff up to 30 s
    - Other API errors: exponential backoff
    - JSONDecodeError: sanitize and retry, return {} on final failure
    """
    max_tok = max_tokens or settings.OPENAI_MAX_TOKENS

    attempt = 0
    while attempt < retries:
        try:
            response = _client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                max_tokens=max_tok,
                temperature=settings.OPENAI_TEMPERATURE,
                response_format={"type": "json_object"},  # enforces JSON output
            )
            raw = response.choices[0].message.content.strip()
            return _parse_json(raw)

        except RateLimitError:
            wait = min(2 ** attempt, 30)
            logger.warning(f"OpenAI rate limit — waiting {wait}s (attempt {attempt + 1})")
            time.sleep(wait)
            attempt += 1

        except APIError as e:
            logger.error(f"OpenAI API error on attempt {attempt + 1}: {e}")
            if attempt >= retries - 1:
                raise
            time.sleep(2)
            attempt += 1

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error on attempt {attempt + 1}: {e} — retrying")
            if attempt >= retries - 1:
                logger.error("JSON parse failed on all attempts — returning empty dict")
                return {}
            time.sleep(1)
            attempt += 1

    raise RuntimeError("OpenAI API call failed after all retries")


def _parse_json(raw: str) -> dict:
    """Strip markdown code fences, sanitize bad escapes, and parse JSON."""
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        sanitized = re.sub(r'\\(?![\"\\/bfnrtu])', r'\\\\', cleaned)
        return json.loads(sanitized)

