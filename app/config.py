from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # OpenAI API
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 4096
    OPENAI_TEMPERATURE: float = 0.3

    # IONOS Exchange Email (info@das-elb.de — Microsoft Exchange account)
    # ⚠️  info@das-elb.de is on IONOS Exchange — use Exchange servers, NOT imap.ionos.com
    HOTEL_EMAIL: str = "info@das-elb.de"
    IONOS_IMAP_HOST: str = "exchange.ionos.eu"        # IONOS Exchange IMAP server (✅ confirmed)
    IONOS_IMAP_PORT: int = 993                         # SSL/TLS
    IONOS_SMTP_HOST: str = "smtp.exchange.ionos.eu"   # IONOS Exchange SMTP server (✅ confirmed)
    IONOS_SMTP_PORT: int = 587                         # STARTTLS (not 465 SSL)
    IONOS_EMAIL_PASSWORD: str = ""  # Set in .env — never commit to git

    # Hotel APIs (existing, no changes needed)
    HOTEL_MGMT_API_BASE: str = (
        "https://daselb-management-os-v2-api-912934217177.europe-west3.run.app"
    )
    RESERVATIONS_API_BASE: str = "https://das-elb-backend.onrender.com"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./daselb_agent.db"

    # Polling
    POLL_INTERVAL_SECONDS: int = 180

    # Dashboard security
    DASHBOARD_API_KEY: str = "change-me"
    CORS_ORIGINS: str = "http://localhost:3001"

    # Twilio (optional — Phase 3)
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_WHATSAPP_FROM: Optional[str] = None
    MANAGER_WHATSAPP: Optional[str] = None

    # Feature flags
    ENABLE_AUTO_SEND: bool = False           # NEVER set true without extensive review
    ENABLE_WHATSAPP_NOTIFICATIONS: bool = False
    ENABLE_COMPETITOR_RATES: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
