from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    POLL_INTERVAL: float = 1.0
    PING_TARGETS: List[str] = ["8.8.8.8", "1.1.1.1"]
    HTTP_TARGETS: List[str] = ["https://www.google.com", "https://www.cloudflare.com"]
    TIMEOUT: float = 0.5
    MAX_BUFFER_SIZE: int = 3600  # 1 hour at 1s interval
    DATABASE_URL: str = "sqlite+aiosqlite:///./connectivity.db"
    WIFI_POLL_INTERVAL: float = 10.0  # Fetch WiFi info every 10s
    IP_POLL_INTERVAL: float = 300.0   # Fetch public IP every 5 minutes
    IP_CHECK_URL: str = "https://api.ipify.org"
    
    # Latency thresholds (ms)
    LATENCY_WARNING: float = 250.0
    LATENCY_CRITICAL: float = 500.0
    # Custom thresholds for specific targets
    CUSTOM_THRESHOLDS: dict = {}

    class Config:
        env_file = ".env"

settings = Settings()
