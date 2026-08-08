# Privacy Policy for PRScope

**Last Updated:** August 2026

PRScope is built as a developer tool designed with privacy in mind. This privacy policy explains what data we collect, why we collect it, and how it is handled.

## 1. Information We Collect
When you use the PRScope Chrome Extension, we handle the following data:
*   **Authentication Information:** Logging in via GitHub OAuth is required to run any pull request analysis. On login, we store your GitHub profile identifier, username, and avatar URL to maintain your session and, if you use it, your "Saved Reviews" workspace. We do not access or store your real email address, even though the GitHub OAuth consent screen currently requests email read access.
*   **API Keys and Tokens (BYOK):** If you provide your own Gemini, OpenAI, or Groq API key, or a GitHub Personal Access Token (used to post review comments on your behalf, publish commit statuses, and verify repository access for the Team Reviews feature described below), these are stored **locally in your browser only, in plaintext (not encrypted)**, and sent only to our backend as part of your own requests. We do not have server-side access to these values outside of the request you initiate.
*   **Website Content:** To generate pull request reviews, the extension reads the text, diffs, and structure of the GitHub Pull Request you are currently viewing.

## 2. How We Use the Information
*   **Core Functionality:** Your pull request data is securely transmitted to our backend API solely for the purpose of generating the AI code review, risk assessment, and architectural analysis.
*   **No Data Selling:** We do not sell, rent, or share your code, personal data, or API keys with any third-party advertisers or brokers.

## 3. Data Storage
*   API keys and GitHub tokens you provide are stored locally in your browser's local storage, unencrypted. They are not stored on our servers. Use a scoped, minimally-privileged GitHub token where possible.
*   Logging in creates a persistent user profile record (GitHub ID, username, avatar URL) on our backend, independent of whether you save any reviews.
*   Pull request analysis results are processed by the backend and are only stored persistently if you use the "Saved Reviews" feature to track review status and notes.
*   **Team Reviews visibility:** by default, your saved reviews (including your notes and the generated summary) are private to your account. If you switch on the "Team Reviews" view for a repository, and supply a GitHub Personal Access Token that we verify has real access to that repository (write access for public repos; any access for private repos, since GitHub itself does not reveal a private repo's existence to non-collaborators), you will be shown other PRScope users' saved reviews for that same repository, and they may see yours under the same condition. This sharing is scoped strictly to the repository you verify access to, is opt-in per view, and does not apply to repositories you have not explicitly requested the Team Reviews view for.

## 4. Third-Party Services
Depending on which provider you configure, we send code diffs and PR context to Google's Gemini API or OpenAI's API to generate reviews, in accordance with each provider's respective API usage and data policies. If you have not configured your own key, requests may use a shared backend-managed key subject to the same third-party policies.

## 5. Contact
Since PRScope is an open-source tool, you can inspect the code, open an issue, or contact the developer directly via our GitHub repository: https://github.com/kankaniakshat185/prscope-pr-review-intelligence

For privacy-related inquiries, you can also contact us at kankaniakshat185@gmail.com.
