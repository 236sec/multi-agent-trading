from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator
import yaml


class WatchlistItem(BaseSettings):
    ticker: str
    sector: str


class RiskConfig(BaseSettings):
    max_position_pct: float = 0.20
    max_sector_pct: float = 0.40
    max_drawdown_pct: float = 0.15


class ModelConfig(BaseSettings):
    path: str = "models/signal_v1.pkl"


class ScheduleConfig(BaseSettings):
    data_ingestion_time: str = "16:30"
    signal_time: str = "17:00"
    risk_time: str = "17:30"


class BrokerConfig(BaseSettings):
    mode: str = "paper"  # paper or live


class Settings(BaseSettings):
    # From .env
    database_url: str = "postgresql://localhost:5432/trading"
    webull_api_key: Optional[str] = None
    webull_api_secret: Optional[str] = None
    webull_account_id: Optional[str] = None

    # From config.yaml
    watchlist: list[WatchlistItem] = []
    risk: RiskConfig = RiskConfig()
    model: ModelConfig = ModelConfig()
    schedule: ScheduleConfig = ScheduleConfig()
    broker: BrokerConfig = BrokerConfig()

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("watchlist", "risk", "model", "schedule", "broker", mode="before")
    @classmethod
    def load_yaml(cls, v, info):
        """Load defaults from config.yaml if they exist."""
        config_path = Path("config.yaml")
        if config_path.exists():
            with open(config_path) as f:
                yaml_data = yaml.safe_load(f) or {}
            field_name = info.field_name
            if field_name in yaml_data:
                return yaml_data[field_name]
        return v


def get_settings() -> Settings:
    return Settings()
