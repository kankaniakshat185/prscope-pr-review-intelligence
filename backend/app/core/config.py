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

    # How long the webhook receiver waits after the *last* pull_request
    # event for a given PR before actually running analysis. A quick series
    # of pushes fires several `synchronize` events in a row; without this,
    # each would trigger its own full analysis run instead of one run
    # reflecting the final state.
    WEBHOOK_DEBOUNCE_SECONDS: float = 30.0

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
    #
    # Chrome assigns a *different* extension ID to an unpacked "Load
    # unpacked" install than the published Chrome Web Store ID - the ID is
    # derived from the absolute path of the unpacked folder. Loading
    # unpacked from a new/different path will mint yet another ID and need
    # adding here too.
    #   jfngcklfbiljgpoeehlkpkackahgopoc - published Chrome Web Store ID
    #   gimimplokapoleofedgmdnghpcdhkmhm - unpacked dev install
    ALLOWED_ORIGINS: str = "chrome-extension://jfngcklfbiljgpoeehlkpkackahgopoc,chrome-extension://gimimplokapoleofedgmdnghpcdhkmhm,http://localhost:3000"

    class Config:
        env_file = ".env"

settings = Settings()
