from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    env: str = "dev"
    log_level: str = "INFO"
    gateway_url: str = "http://localhost:8080"
    # Never hard-code secrets. Load from environment / secret manager.
    model_api_key: str = ""

    class Config:
        env_file = ".env"
