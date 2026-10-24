from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # watsonx.ai credentials
    watsonx_api_key: str = ""
    watsonx_project_id: str = ""
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"
    watsonx_text_model: str = "ibm/granite-3-3-8b-instruct"
    watsonx_vision_model: str = "ibm/granite-vision-3-2-2b"
    watsonx_vision_enabled: bool = True

    # Risk thresholds
    high_risk_threshold: float = 0.65
    medium_risk_threshold: float = 0.35

    # Relevance & look-ahead
    max_relevance_distance_m: float = 500.0
    look_ahead_seconds: float = 8.0

    # Freshness / expiry (seconds)
    freshness_full_seconds: float = 10.0
    freshness_moderate_seconds: float = 30.0
    hazard_expiry_seconds: float = 120.0

    # Physics / conflict detection
    braking_threshold_ms2: float = -4.0
    conflict_window_seconds: float = 2.0
    max_ttc_seconds: float = 10.0

    # Telemetry rate-limiting
    telemetry_rate_limit_seconds: float = 1.0

    # Maneuver zone
    maneuver_zone_radius_m: float = 150.0


settings = Settings()
