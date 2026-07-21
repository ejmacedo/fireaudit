from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://fireaudit:fireaudit@postgres:5432/fireaudit"

    # Auth
    jwt_secret: str = "changeme-generate-a-long-random-value"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30

    # CORS
    frontend_origin: str = "http://localhost:3000"

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id_pro: str = ""
    stripe_success_url: str = "http://localhost:3000/dashboard?checkout=success"
    stripe_cancel_url: str = "http://localhost:3000/dashboard?checkout=cancel"

    # KMS
    kms_provider: str = "local"
    kms_key_ocid: str = ""

    # Sentry
    sentry_dsn: str = ""

    # Analysis engine
    agent_offline_threshold_minutes: int = 30
    expiring_cert_threshold_days: int = 30

    # Environment
    environment: str = "development"


settings = Settings()
