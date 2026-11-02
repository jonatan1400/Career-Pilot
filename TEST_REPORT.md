# Verification report — November 2, 2026

## Executed successfully

- Python compilation of all application, test, and live-smoke-test source files.
- **11 dependency-free automated tests:** text cleanup; empty and oversized text; upload size checks; unsupported extensions; short-document grounding; retrieval of relevant evidence near the end of a long document; empty grounding; quota expiration; concurrent quota enforcement; Markdown escaping.
- Manual source review of secret handling, profile sharing/invalidation, interview transition ordering, error preservation, and deployment packaging. Source review is not equivalent to runtime testing.

## Not verified in this environment

- Dependency installation failed because the execution environment could not resolve/reach the Python package registry. The bundled dependency-runtime lookup was also unavailable.
- PDF/DOCX parser tests, Pydantic/OpenAI integration tests, and Streamlit UI tests are written but **not executed** because their dependencies could not be installed.
- The application has **not been launched or visually inspected** on desktop/mobile browsers.
- No OpenAI API key was configured. **No real AI responses were generated or evaluated.**
- Streamlit Community Cloud opened to its sign-in page. No authenticated deployment access or GitHub repository was available. **No deployment was created; no public URL exists.**

## Included tests awaiting execution

`tests/test_documents.py`: valid generated PDF and DOCX including Word tables, blank/scanned-like PDF, encrypted PDF, corrupt PDF/DOCX.

`tests/test_ai.py`: successful structured request, store=False and grounding policy, invalid/refused/incomplete outputs, missing key, authentication failure, provider rate limit, connectivity failure, unexpected error sanitization, evidence sections.

`tests/test_app.py`: navigation retaining the profile, clearing session information, missing-input gating, multiple interview turns, API failure preserving answers, resume/roadmap result rendering and retention. Tests use mocked API transport; these do not validate live AI quality.

`scripts/smoke_live.py`: seven explicit billable real requests covering resume analysis, roadmap, two question/answer evaluations, and interview summary. Requires a privately configured key and working network. It validates structured outputs, not correctness of all recommendations.

## Public-release checklist

After installing dependencies, run `python -m pytest -q` and fix any failures. Then run the live smoke test with a developer key in the local environment. In the web interface, enter your own key in the sidebar.

On the actual hosted URL:

1. Open a private/incognito browser window. Confirm access without a student account.
2. Upload a valid text PDF resume; inspect extracted text, then save. Repeat with a DOCX resume, including a table. Check that no resume data is visible in another browser session.
3. Paste a vacancy; generate a resume assessment. Check that evidence matches the resume, rewrites preserve actual facts, no achievements or metrics are invented, and gaps distinguish missing documentation from confirmed skill gaps.
4. Generate a roadmap; inspect feasibility, relevance to existing knowledge, priority order, and distinct 30/60/90-day deliverables. Remove the vacancy and verify a general-role assessment is clearly labeled.
5. Complete at least two interview answers. Verify one question at a time, specific feedback, grounded example answers, next-question behavior, and end summary. Check both behavioral and technical modes, plus Mixed alternation.
6. Switch pages and return; confirm saved profile, results, and interview history persist. Save a changed profile and confirm old results/interview are removed.
7. Test a blank answer, absent required input, corrupted file, scanned PDF, oversized upload, and unsupported type. Ensure useful messages and no ungrounded fallback analysis.
8. On a staging copy, test a missing/invalid student API key and simulated provider failures. Ensure inputs/answers survive and no raw exceptions, credentials, or personal content are exposed. Verify rate-limit messages.
9. Clear session data; verify the API key and all profile fields, uploads, results, and conversation content disappear. Confirm anonymous rate-limit counters persist.
10. Repeat the main workflow on a mobile browser; inspect sidebar navigation, readable results, form widths, and interview controls.
11. Record the actual public URL, deployment date, dependency versions, model, test outcomes, and any unresolved issues here before claiming production readiness.

## Per-user API key update

The web app now requires each student to enter their own key in a password field. There is no owner-key fallback. The key stays in session state and is passed only to the OpenAI client, not to model context. Dedicated key removal and full session clearing are provided. Added Streamlit coverage for key persistence across navigation, removal, and lack of environment-key fallback; these dependency-based tests remain unexecuted. Syntax compilation and the 11 dependency-free tests pass after this change.
