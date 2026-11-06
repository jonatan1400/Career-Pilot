# CareerPilot AI

A Streamlit coaching app for college students. Students bring their own OpenAI API key, save one profile (target role, background, resume, and an optional job description), and use three tools that share it:

1. **Resume Analyzer** – alignment with a specific vacancy, evidence-backed strengths, gaps, verified bullet rewrites, keywords, and priorities.
2. **Career Roadmap** – skills to build on, skills to develop by priority, projects, and a 30/60/90-day plan.
3. **Interview Coach** – one question at a time, structured feedback on six dimensions, and an end-of-session summary.

All model output is validated against the Pydantic schemas in `models.py`, and the app never writes student content to disk.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
streamlit run app.py
```

Open http://localhost:8501, paste an OpenAI API key in the sidebar, and either fill in the profile page or press **Try with sample data** to load a short fictional profile.

Optional settings (environment variables or `.streamlit/secrets.toml`):

| Setting | Default | Purpose |
| --- | --- | --- |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Model used for every request |
| `SESSION_HOURLY_LIMIT` | `25` | AI requests per browser session per hour |
| `GLOBAL_HOURLY_LIMIT` | `100` | AI requests across all sessions per hour |

## Tests

```bash
python -m pytest -q
```

`tests/test_core.py` is dependency-free; the other suites need the packages in `requirements-dev.txt`. The Streamlit tests mock the OpenAI transport. `scripts/smoke_live.py` makes seven real, billable requests and needs `OPENAI_API_KEY` in the environment.

## Project layout

| Path | Role |
| --- | --- |
| `app.py` | Streamlit interface: sidebar, pages, and result rendering |
| `styles.css`, `.streamlit/config.toml` | Theme and interface styles |
| `ai_service.py` | Prompts, structured-output requests, and post-validation |
| `models.py` | Output schemas |
| `documents.py` | PDF/DOCX extraction, size limits, and evidence-section retrieval |
| `limits.py` | Shared hourly usage limiter |
| `formatting.py` | Markdown escaping for untrusted text |
| `Dockerfile` | Container image (`streamlit run app.py` on port 8501) |

## Privacy notes

Keys, documents, and answers live only in the active server session. Requests to OpenAI are sent with `store=False`, and the app has no database or document logging. Uploaded files are parsed in memory with a 5 MB / 20-page cap. Students can remove their key or clear the whole session from the sidebar at any time.
