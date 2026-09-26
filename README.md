<h1 align="center">PRScope - PR Review Intelligence</h1>
<img width="1469" height="704" alt="Screenshot 2026-09-27 at 1 13 22 AM" src="https://github.com/user-attachments/assets/a00c47f2-7567-490e-bea0-651642161d4a" />

**Live Demo:** [Install PRScope from the Chrome Web Store](https://chromewebstore.google.com/detail/prscope/jfngcklfbiljgpoeehlkpkackahgopoc)




PRScope is a full-stack Chrome Extension and FastAPI platform that performs instant, comprehensive pull request reviews natively within the GitHub UI. It acts as an autonomous agent that deeply analyzes structural code changes, flags common known-vulnerability patterns, maps downstream dependency impacts, and generates actionable, 1-click inline code comments using advanced LLM reasoning.

Built for high-velocity engineering teams, PRScope significantly reduces the cognitive overhead required to review massive legacy refactors, complex dependency chains, and subtle architectural anti-patterns. Stop blindly merging code and gain deterministic x-ray vision into every pull request.

## Features

- **Deterministic Risk Assessment** — Risk score + reviewability index from real heuristics (LOC volatility, symbol density, test coverage, cyclomatic complexity via actual control-flow graphs) — not LLM output.
- **Security & Architecture Auditing** — Bandit-based vulnerability scanning and AST-based import/architecture rule enforcement for Python, pattern-based fallback for other languages, with support for custom per-repo rules (`.prscope.yml`).
- **Multi-Language Dependency Graph** — Real call-graph construction from actual file content (Python `ast`, JS/TS via tree-sitter), plus an opt-in, incrementally-updated full-repo index surfacing cross-file "blast radius" callers a single-PR diff would miss.
- **AI-Assisted Review** — LLM-generated executive summaries, review checklists, and inline comment suggestions cross-referenced against Jira/Linear context — kept fully separate from the deterministic analysis above.
- **Historical Incident Matching** — Retrieval-augmented matching against 15 real, sourced software incidents plus team-contributed ones, with measured retrieval quality (93% precision@1) on a labeled evaluation set.
- **Team Collaboration** — Shared review visibility across teammates, gated on a live GitHub permission check (not just review history), and a team-contributed incident database.
- **GitHub Integration** — Posts AI comments and publishes risk verdicts as commit statuses directly to the PR; optional signature-verified webhooks auto-trigger debounced analysis on push.
- **Bring Your Own Key** — Use your own Gemini, OpenAI, or Groq key to bypass the shared rate-limited pool.
- **Fast & Reliable** — Deterministic results return in under a second, independent of AI content; LLM calls are batched down to 2 per analysis with retry/backoff and structured-output enforcement across all three providers.


## Security Model

- **Login required.** Every analysis request and workspace operation requires a valid GitHub-issued session (JWT bearer token) — there is no anonymous access to `/analyze`.
- **JWT signing key is mandatory.** `JWT_SECRET` has no default and no fallback; the backend refuses to start without it. Rotate it and every existing session is invalidated.
- **Mock login is dev-only and off by default.** `ENABLE_MOCK_AUTH=true` unlocks a passwordless login path (`code=mock`) that skips GitHub OAuth entirely — never enable this on a deployed instance.
- **CORS is allow-listed, not wildcard.** Only the origins in `ALLOWED_ORIGINS` (the published extension ID + any local dev origins you add) can call the API.
- **Webhooks are signature-verified.** `GITHUB_WEBHOOK_SECRET` must be set and must match the secret configured on the GitHub webhook, or every event is rejected.
- **BYOK keys are stored, not encrypted.** Gemini/OpenAI/Groq keys and your GitHub PAT live in the extension's local storage in plaintext. Use scoped, minimally-privileged tokens.
- **Team-shared saved reviews require a verified GitHub permission check.** Viewing another user's saved review for a repository requires a live GitHub API check (via your own PAT) proving real access to that repo — not merely having used PRScope on it before. See Team-Shared Saved Reviews above.

## System Architecture

The platform follows a decoupled client-server model: the Chrome Extension stays lightweight and talks to a single FastAPI backend, which owns all LLM inference, deterministic analysis, persistence, and the outbound calls to GitHub's API.

```mermaid
graph TD
    subgraph Client [Chrome Extension]
        CS[Content Script<br/>injects iframe on github.com/*/pull/*]
        BS[Background Worker<br/>on-demand injection]
        UI[Next.js React UI<br/>runs inside the iframe]
        Storage[(localStorage<br/>JWT session, BYOK keys, GitHub PAT)]
    end

    subgraph Backend [FastAPI Backend]
        CORS{CORS gate<br/>allow-listed origins only}
        Auth[Auth: GitHub OAuth + JWT<br/>mock login gated, dev-only]
        API[Analysis API<br/>requires bearer token · split: fast /analyze + slower /analyze/enrich]
        Engines[Deterministic Engines<br/>risk · reviewability · security ·<br/>architecture · dependency graph · symbols]
        Indexer[Repo Index Engine<br/>full + incremental, background task]
        LLMSvc[LLM Service<br/>thread-pool offloaded, timeout-bounded]
        Webhook[Webhook Receiver<br/>HMAC-SHA256 verified · debounced auto-analysis]
    end

    subgraph Data [Persistence]
        DB[(SQLite or PostgreSQL<br/>users, saved reviews, repo-wide function/call index)]
        Chroma[(ChromaDB<br/>15 real sourced incidents + team-contributed)]
    end

    subgraph External [External Services]
        GH[GitHub REST API<br/>OAuth, PR data, issue comments, commit statuses]
        Gemini[Google Gemini API]
        OpenAI[OpenAI API]
        Groq[Groq API<br/>OpenAI-compatible]
    end

    BS -->|chrome.scripting.executeScript| CS
    CS <-->|postMessage, origin-checked both ways| UI
    UI -->|fetch, Bearer JWT| CORS --> API
    Storage -.->|session + BYOK keys| UI

    API --> Auth
    Auth -->|OAuth code exchange| GH
    Auth --> DB
    API --> Engines
    Engines -->|fetch PR diff, files & base/head content| GH
    Engines -.->|read: cross-file blast radius| DB
    API -->|post comments/statuses & verify repo access, user-supplied PAT| GH
    Engines -->|read: similarity search| Chroma
    API -->|write: report a team incident| Chroma
    API --> LLMSvc
    LLMSvc --> Gemini
    LLMSvc --> OpenAI
    LLMSvc --> Groq
    API --> DB
    API -->|explicit build/refresh request| Indexer
    Indexer -->|fetch full tree, changed files| GH
    Indexer -->|write: functions & call edges| DB

    GH -->|pull_request events| Webhook
    Webhook -->|debounced| Engines
    Webhook -.->|refresh if already indexed| Indexer
    Webhook -->|risk verdict as commit status| GH
```

## Usage Guide

To use the PRScope extension effectively on any GitHub repository:

1. **Installation:** [Install PRScope from the Chrome Web Store](https://chromewebstore.google.com/detail/prscope/jfngcklfbiljgpoeehlkpkackahgopoc), or load the unpacked `extension/out` directory locally (see Extension Setup below).
2. **Navigate to a PR:** Open any active Pull Request on GitHub. You will notice the PRScope interface seamlessly injected into the GitHub sidebar or as a floating panel upon clicking the PRScope icon in the extensions bar.
3. **Authentication (required):** Click "Login with GitHub" to authenticate and generate a session token. Analysis will not run until you're logged in — you'll see a "Login Required" prompt otherwise.
4. **Configure BYOK (Optional but Recommended):** Click the **Settings (⚙️)** gear icon in the top right corner of the extension and enter your personal Gemini or OpenAI API key to bypass global rate limits and ensure unrestricted analysis. These are stored locally, unencrypted — see Security Model above.
5. **Run Analysis:** The extension automatically reads the PR diff, context, and issue descriptions. It will present a comprehensive Risk Assessment, Dependency Graph, Security Findings, and actionable Review Comments.
6. **Save Snapshots:** Use the "Copy Snapshot" button to instantly copy the AI-generated executive summary and findings to your clipboard, ready to be pasted as a formal GitHub review.

## Local Development Initialization

To run the application locally for contribution or self-hosting, follow the steps below.

### Prerequisites
- Python 3.11.x (recommended and pinned in CI — newer versions may lack prebuilt wheels for some pinned dependencies, notably `pydantic-core`)
- Node.js 18+
- PostgreSQL instance (or SQLite, the default, for local testing)
- Google Gemini and/or OpenAI API Key
- GitHub OAuth Application Credentials

### Backend Setup

1. Navigate to the backend directory and establish a virtual environment:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies (pinned — see `requirements.txt`):
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
```
Then fill in `backend/.env`. At minimum you need a `JWT_SECRET` — the app will not start without one:
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
See `.env.example` for the full list (`DATABASE_URL`, `GITHUB_CLIENT_ID`/`SECRET`, `ENABLE_MOCK_AUTH`, `GITHUB_WEBHOOK_SECRET`, `ALLOWED_ORIGINS`, LLM provider keys). Notes:
- Without a GitHub OAuth app configured, set `ENABLE_MOCK_AUTH=true` to log in locally without one — never set this in a deployed environment.
- `ALLOWED_ORIGINS` defaults to the published extension's ID; override it if you're running your own fork/build under a different extension ID.

4. Run the test suite:
```bash
pytest
```

5. Initialize the server:
```bash
uvicorn app.main:app --reload --port 8000
```

### Extension Setup

1. Navigate to the extension directory:
```bash
cd extension
npm install
```

2. Execute the build process:
```bash
npm run build
```

3. Load into Chrome:
- Navigate to `chrome://extensions/`
- Enable "Developer mode"
- Select "Load unpacked"
- Target the `extension/out` directory generated by the build process.

### CI

`.github/workflows/ci.yml` runs on every push/PR to `main`: the backend job installs pinned dependencies and runs `pytest`; the extension job typechecks (`tsc --noEmit`), builds the actual Chrome extension bundle, and lints — all blocking.

## License
MIT License. See `LICENSE` for more information.
