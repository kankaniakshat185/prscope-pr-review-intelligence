# PRScope - PR Review Intelligence

[Chrome Web Store Extension Link - Coming Soon]

**Autonomous AI Senior Engineer for GitHub.**

PRScope is a full-stack Chrome Extension and FastAPI platform that performs instant, comprehensive pull request reviews natively within the GitHub UI. It acts as an autonomous agent that deeply analyzes structural code changes, flags common known-vulnerability patterns, maps downstream dependency impacts, and generates actionable, 1-click inline code comments using advanced LLM reasoning.

Built for high-velocity engineering teams, PRScope significantly reduces the cognitive overhead required to review massive legacy refactors, complex dependency chains, and subtle architectural anti-patterns. Stop blindly merging code and gain deterministic x-ray vision into every pull request.

## Core Capabilities

### Deterministic Risk Assessment
Generates a quantifiable Risk Score (1-10) and a Reviewability Index based on rigid heuristics rather than stochastic LLM generation. Evaluates factors such as Line of Code (LOC) volatility, symbol modification density, test coverage deltas, and PR description fidelity to triage the risk of a merge.

### Automated Security & Architecture Auditing
Scans added lines in the diff against a deterministic set of pattern rules (hardcoded credentials, `eval`/`exec`, `shell=True`, unsafe deserialization, f-string SQL interpolation, and similar known-bad patterns) and flags configured module-boundary/import violations. This is single-line pattern matching, not a full SAST engine — it won't catch multi-line, obfuscated, or otherwise disguised issues, and it doesn't detect unknown ("zero-day") vulnerability classes by design.

### Dynamic Architecture Verification (.prscope.yml)
Supports highly customized, repository-specific architectural rules. The engine dynamically fetches and parses `.prscope.yml` definitions from the target repository root, allowing engineering teams to enforce strict, bespoke module boundaries and import restrictions on a per-project basis.

### Causal Dependency Mapping & Visualization
Parses the diff to build a best-effort call graph for **Python files** and renders it as a visual dependency graph in the Chrome Extension UI. The graph is built from diff context only (not the full file or full repository), so accuracy is naturally limited to what's visible in the patch, and non-Python files currently don't produce a dependency graph.

### Stateful Review Generation
Cross-references the pull request diff against provided Jira/Linear ticket context to ensure strict adherence to business requirements. Generates highly contextual, actionable inline comments that can be directly submitted to the GitHub timeline via the extension UI.

### Bring Your Own Key (BYOK) Architecture
Users can bypass the shared API quota pool by supplying their own Gemini or OpenAI API key, persisted in the browser's local storage. Note this storage is **not encrypted** — treat it like any other locally-cached credential, and prefer a scoped/limited-privilege key where possible.

### GitHub Webhook Ingestion (signature-verified, foundation only)
The FastAPI backend exposes a signature-verified `pull_request` webhook receiver (`opened`, `synchronize`, `reopened`), gated by `GITHUB_WEBHOOK_SECRET`. Today it validates and logs the event; it does not yet dispatch analysis automatically. It's built as the foundation for future CI/CD-triggered background analysis (e.g. via a task queue), not a shipped feature yet.

### Resilient Inference & Rate Limit Handling
The LLM service layer implements robust exception boundaries to handle upstream API quotas gracefully. If global rate limits (HTTP 429) are exceeded, the platform automatically degrades into a deterministic heuristic mode, ensuring risk scores and dependency graphs are reliably delivered even during inference outages.

## System Architecture

The platform follows a decoupled client-server model, ensuring the Chrome Extension remains lightweight while offloading heavy LLM inference, embedding generation, and vector storage to a distributed backend.

```mermaid
graph TD
    subgraph Client [Chrome Browser]
        UI[Next.js React UI]
        CS[Content Scripts]
        BS[Background Service Worker]
        Storage[(Local Storage)]
    end

    subgraph Backend [FastAPI Application Layer]
        API[API Router]
        Auth[OAuth Provider]
        Risk[Risk & Telemetry Engine]
        LLM[LLM Service Abstraction]
    end

    subgraph Infrastructure [Data & Inference]
        PG[(Neon PostgreSQL)]
        Chroma[(ChromaDB Vector Store)]
        Gemini[Google Gemini API]
    end

    UI <-->|DOM Injection| CS
    CS <-->|Messaging| BS
    BS <-->|HTTPS REST| API
    Storage -.->|BYOK Key| BS

    API --> Auth
    Auth --> PG
    API --> Risk
    API --> LLM

    LLM --> Chroma
    LLM --> Gemini
```

## Usage Guide

To use the PRScope extension effectively on any GitHub repository:

1. **Installation:** Install the extension from the Chrome Web Store (or load the unpacked `out` directory locally).
2. **Navigate to a PR:** Open any active Pull Request on GitHub. You will notice the PRScope interface seamlessly injected into the GitHub sidebar or as a floating panel.
3. **Authentication:** Click the "Login with GitHub" button within the extension to securely authenticate and generate a session token.
4. **Configure BYOK (Optional but Recommended):** Click the **Settings (⚙️)** gear icon in the top right corner of the extension and enter your personal Google Gemini API Key to bypass global rate limits and ensure unrestricted analysis.
5. **Run Analysis:** The extension automatically reads the PR diff, context, and issue descriptions. It will present a comprehensive Risk Assessment, Dependency Graph, Security Findings, and actionable Review Comments.
6. **Save Snapshots:** Use the "Copy Snapshot" button to instantly copy the AI-generated executive summary and findings to your clipboard, ready to be pasted as a formal GitHub review.

## Local Development Initialization

To run the application locally for contribution or self-hosting, follow the steps below.

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL instance (or SQLite for testing)
- Google Gemini API Key
- GitHub OAuth Application Credentials

### Backend Setup

1. Navigate to the backend directory and establish a virtual environment:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables in `backend/.env`:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/prscope
GEMINI_API_KEY=your_gemini_api_key
GITHUB_CLIENT_ID=your_oauth_client_id
GITHUB_CLIENT_SECRET=your_oauth_client_secret
JWT_SECRET=secure_jwt_signing_key
```

4. Initialize the server:
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

## License
MIT License. See `LICENSE` for more information.
