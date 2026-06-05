from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "PRScope Backend"
    DATABASE_URL: str = "sqlite:///./prscope.db"
    GITHUB_TOKEN: str = ""
    GEMINI_API_KEY: str = ""
    CHROMA_DB_DIR: str = "./chroma_db"
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
