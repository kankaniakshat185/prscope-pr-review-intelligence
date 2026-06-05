# PRScope - GitHub PR Intelligence 

PRScope is a Chrome Extension that injects a right-hand sidebar into GitHub Pull Request pages. It provides a deterministic risk engine, dependency impact analysis, architecture validation, incident similarity check, and Gemini-based review checklists and suggested comments.

## Tech Stack
- **Frontend**: Next.js 15, Tailwind CSS, shadcn/ui
- **Backend**: FastAPI, PostgreSQL, ChromaDB, Gemini 2.5 Flash

## How to use

### 1. Start the Backend
Navigate to the `backend` directory and install the requirements:
```bash
cd backend
pip install -r requirements.txt
```

Run the FastAPI server:
```bash
uvicorn app.main:app --reload
```
The server will run on `http://localhost:8000`. Ensure PostgreSQL is running. (Database connection string is in `backend/.env`).

### 2. Load the Chrome Extension
The extension has already been built into the `extension/out` directory.

1. Open Google Chrome.
2. Navigate to `chrome://extensions/`.
3. Enable **Developer mode** in the top right corner.
4. Click **Load unpacked**.
5. Select the `extension/out` directory in your file browser.

### 3. Test on GitHub
Navigate to any GitHub Pull Request page.
The extension will inject a sidebar on the right side with the PR analysis.

*Note: Since the backend currently uses Gemini, be sure to set `GEMINI_API_KEY` in `backend/.env` for LLM features to work.*
