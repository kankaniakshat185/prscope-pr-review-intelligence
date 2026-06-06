# PRScope - PR Review Intelligence

[Chrome Web Store Extension Link - Coming Soon]

**Autonomous AI Senior Engineer for GitHub.**

PRScope is a full-stack Chrome Extension and FastAPI platform that performs instant, comprehensive pull request reviews natively within the GitHub UI. It acts as an autonomous agent that deeply analyzes structural code changes, catches zero-day vulnerabilities, maps downstream dependency impacts, and generates actionable, 1-click inline code comments using advanced LLM reasoning.

Built for high-velocity engineering teams, PRScope significantly reduces the cognitive overhead required to review massive legacy refactors, complex dependency chains, and subtle architectural anti-patterns. Stop blindly merging code and gain deterministic x-ray vision into every pull request.

## Core Capabilities

### Deterministic Risk Assessment
Generates a quantifiable Risk Score (1-10) and a Reviewability Index based on rigid heuristics rather than stochastic LLM generation. Evaluates factors such as Line of Code (LOC) volatility, symbol modification density, test coverage deltas, and PR description fidelity to triage the risk of a merge.

### Automated Security & Architecture Auditing
Detects common exploitation vectors and architectural abstraction leaks. It systematically flags structural code violations against established design patterns (e.g., SOLID, DRY) and highlights potential zero-day entry points introduced in the diff.

### Dynamic Architecture Verification (.prscope.yml)
Supports highly customized, repository-specific architectural rules. The engine dynamically fetches and parses `.prscope.yml` definitions from the target repository root, allowing engineering teams to enforce strict, bespoke module boundaries and import restrictions on a per-project basis.

### Causal Dependency Mapping & Visualization
Constructs an abstract syntax tree representation of the modifications to map upstream service dependencies and downstream module impacts. Identifies exactly which components of the codebase are at risk of cascading failure and renders a dynamic, visual dependency graph directly within the Chrome Extension UI.

### Stateful Review Generation
Cross-references the pull request diff against provided Jira/Linear ticket context to ensure strict adherence to business requirements. Generates highly contextual, actionable inline comments that can be directly submitted to the GitHub timeline via the extension UI.

### Bring Your Own Key (BYOK) Architecture
Engineered with a primary focus on data sovereignty. Users can bypass the public API quota pool by locally persisting their own Gemini API keys via secure browser storage, enabling unlimited, unrestricted model inference.

### Asynchronous Webhook Integration
Engineered for scale, the FastAPI backend features native GitHub Webhook ingestion. The platform autonomously listens for `pull_request` lifecycle events (opened, synchronized, reopened) to trigger background analysis, paving the way for CI/CD integration and decoupled task queue processing.

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
