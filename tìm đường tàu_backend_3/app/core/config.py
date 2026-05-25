from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:123@localhost:5432/tokyoMap"
    SECRET_KEY: str = "123"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 ngày

    class Config:
        env_file = ".env"

# QUAN TRỌNG: Mày phải có dòng này ở dưới cùng sát lề trái
settings = Settings()