from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "PR Copilot Backend"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/prcopilot"
    GITHUB_TOKEN: str = ""
    GEMINI_API_KEY: str = ""
    CHROMA_DB_DIR: str = "./chroma_db"

    class Config:
        env_file = ".env"

settings = Settings()
