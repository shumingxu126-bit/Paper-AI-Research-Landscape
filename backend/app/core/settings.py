from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_env: str = 'dev'
    app_host: str = '0.0.0.0'
    app_port: int = 8000
    database_url: str = 'sqlite:///./research_landscape.db'
    llm_provider: str = 'anthropic'
    anthropic_api_key: str = ''
    anthropic_model: str = 'claude-sonnet-4-20250514'
    minimax_api_key: str = ''
    minimax_model: str = 'MiniMax-M2.5'
    minimax_base_url: str = 'https://api.minimax.io/v1'
    openalex_email: str = ''
    taxonomy_path: str = '../config/taxonomy_full.yaml'
    max_papers_per_route: int = 12
    openalex_per_route: int = 8
    arxiv_per_route: int = 6
    refresh_batch_size: int = 3
    refresh_interval_hours: int = 24
    request_sleep_seconds: float = 0.5
    bootstrap_lookback_days: int = 365
    incremental_lookback_days: int = 7
    bootstrap_openalex_per_page: int = 20
    bootstrap_openalex_max_pages: int = 3
    bootstrap_arxiv_page_size: int = 20
    bootstrap_arxiv_max_pages: int = 2
    cors_origins: str = "http://127.0.0.1:8080,http://localhost:8080,http://127.0.0.1:5500,http://localhost:5500,null"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
