# Phase 2: Implementation Plan - Architect's Review

## Executive Summary & Architectural Reflection

Based on the QA Lead's report, two critical issues exist in our anomaly tracking system: the failure of the Truth Social scraper due to Cloudflare restrictions, and the deprecation of the `google.generativeai` SDK.

Through a multi-faceted architectural review, the following findings were established:

1. **Scraping Architecture & Cloudflare By-pass:**
   - **Initial Hypothesis:** The `cloudscraper` library fails because Truth Social heavily throttles or blocks automated browsers on its web endpoints. Previous implementations relied on `.rss` endpoints on user profiles.
   - **Discovery:** Truth Social has completely removed standard `.rss` endpoints (they now redirect to a Single Page Application HTML). This causes XML syntax errors when parsed.
   - **Alternative RSS Evaluation:** Using aggregators like `rsshub.app` is not viable for production without self-hosting, as public instances restrict access for high-demand feeds.
   - **The Optimal Solution:** Truth Social is built on a Mastodon fork. Testing confirms that its underlying public REST API is fully operational and **does not** trigger Cloudflare browser-verification challenges when queried with `Accept: application/json`.
   - **Conclusion:** We will completely eliminate `cloudscraper` and RSS parsing. Instead, we will directly query the Mastodon-compatible JSON endpoints (`/api/v1/accounts/lookup` and `/api/v1/accounts/{id}/statuses`) using Python's native `urllib.request`. This significantly improves system reliability and reduces dependencies.

2. **Gemini SDK Migration:**
   - **Current State:** The system relies on the legacy `google.generativeai` package.
   - **Future State:** We need to migrate to the new `google-genai` package and update the initialization and inference logic to use the new `genai.Client` architecture.

## Proposed Changes

### 1. Update `truth_social_monitor.py` - API Migration & Scraper Fix
- **Remove** the `cloudscraper` fallback logic and `xml.etree.ElementTree` parsing from `fetch_latest_posts`.
- **Implement** a two-step API resolution:
  1. `GET https://truthsocial.com/api/v1/accounts/lookup?acct={username}` to retrieve the user's numeric `id` (e.g., Donald Trump's ID).
  2. `GET https://truthsocial.com/api/v1/accounts/{id}/statuses` to fetch the recent posts array in JSON format.
- **Add** robust headers (`User-Agent`, `Accept: application/json`) to the `urllib.request` calls.
- **Process** the JSON payload: Map `content` (cleaning HTML with `re.sub` and `html.unescape`), `created_at`, and `url` to our standard internal post dictionary format.

### 2. Update `truth_social_monitor.py` - Gemini GenAI SDK Migration
- **Replace** `import google.generativeai as genai` with `from google import genai`.
- **Refactor Initialization:** Replace `genai.configure(api_key=...)` and `genai.GenerativeModel(...)` with `self.gemini_client = genai.Client(api_key=...)`.
- **Refactor Inference:** Update `self.gemini_model.generate_content(prompt)` to `self.gemini_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)`.

These architectural changes resolve both outstanding QA issues cleanly and position the project for stable, long-term automated analysis.
