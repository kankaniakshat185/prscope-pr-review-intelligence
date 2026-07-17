# Privacy Policy for PRScope

**Last Updated:** June 2026

PRScope is built as a developer tool designed with privacy in mind. This privacy policy explains what data we collect, why we collect it, and how it is handled.

## 1. Information We Collect
When you use the PRScope Chrome Extension, we handle the following data:
*   **Authentication Information:** If you choose to log in via GitHub OAuth, we securely process your OAuth token to authenticate your requests. If you provide a personal Gemini API Key (BYOK), it is stored locally on your device and transmitted directly to the backend for analysis.
*   **Website Content:** To generate pull request reviews, the extension reads the text, diffs, and structure of the GitHub Pull Request you are currently viewing.

## 2. How We Use the Information
*   **Core Functionality:** Your pull request data is securely transmitted to our backend API solely for the purpose of generating the AI code review, risk assessment, and architectural analysis. 
*   **No Data Selling:** We do not sell, rent, or share your code, personal data, or API keys with any third-party advertisers or brokers.

## 3. Data Storage
*   API keys provided by the user are stored locally in your browser's secure extension storage.
*   Pull request reviews are temporarily processed by the backend and are only stored persistently if you are logged in to track your "Saved Reviews" history.

## 4. Third-Party Services
We use Google's Gemini LLM to generate the reviews. Code diffs are sent to the LLM for analysis in accordance with their API usage policies.

## 5. Contact
Since PRScope is an open-source tool, you can inspect the code, open an issue, or contact the developer directly via our GitHub repository: https://github.com/kankaniakshat185/prscope

For privacy-related inquiries, you can also contact us at kankaniakshat185@gmail.com.
