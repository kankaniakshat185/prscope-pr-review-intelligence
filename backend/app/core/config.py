from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "PRScope Backend"
    DATABASE_URL: str = "sqlite:///./prscope.db"
    GITHUB_TOKEN: str = ""
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    CHROMA_DB_DIR: str = "./chroma_db"
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_WEBHOOK_SECRET: str = ""

    # Required: no default. Startup fails if this isn't set, by design —
    # a hardcoded fallback here previously meant every deployment signed
    # JWTs with a secret visible in the public repo.
    JWT_SECRET: str

    # Off by default. When true, GET /auth/github/callback?code=mock issues
    # a valid session without going through GitHub OAuth. Local dev only —
    # never enable this on a deployed instance.
    ENABLE_MOCK_AUTH: bool = False

    # Comma-separated list of allowed CORS origins (browser extension +
    # any locally-run frontend). No wildcard: this API issues bearer
    # tokens and must not be callable from arbitrary origins.
    ALLOWED_ORIGINS: str = "chrome-extension://jfngcklfbiljgpoeehlkpkackahgopoc,http://localhost:3000"

    class Config:
        env_file = ".env"

settings = Settings()
