# AnchorHandover — Evidence-First, Permission-Aware Handover System

> *"Prevent Critical Knowledge From Leaving With People."*

AnchorHandover is a single-repo **Python + Streamlit** multipage application (no separate backend API, no React, no auth providers) backed by **SQLite via SQLAlchemy**, **Pydantic**, **pandas**, **rapidfuzz**, **pypdf**, **requests**, and **reportlab**. It reconstructs the current state of a project from authorised sources (`git`, `chat`, `ticket`, `doc`, PDFs via `pypdf`, and public GitHub repositories via REST `requests`) into typed, versioned, auditable claims and delivers an approved, role-appropriate handover.

## Repository Structure

- [`app.py`](app.py) — Streamlit multipage entry shell (sidebar Demo Role Selector, LLM provider switcher, session manager, and workflow stepper)
- [`pages/`](pages/) — Five-stage workflow UI: [`1_Connect.py`](pages/1_Connect.py), [`2_Reconstruct.py`](pages/2_Reconstruct.py), [`3_Verify.py`](pages/3_Verify.py), [`4_Review.py`](pages/4_Review.py), [`5_Handover.py`](pages/5_Handover.py)
- [`core/`](core/) — Core domain & security engine:
  - [`models.py`](core/models.py), [`db.py`](core/db.py), [`ingest.py`](core/ingest.py), [`redact.py`](core/redact.py), [`llm.py`](core/llm.py), [`extract.py`](core/extract.py), [`verify.py`](core/verify.py), [`conflicts.py`](core/conflicts.py), [`gaps.py`](core/gaps.py), [`handover.py`](core/handover.py), [`export.py`](core/export.py)
- [`data/synthetic/`](data/synthetic/) — Synthetic demo projects, members (`@synthetic.invalid`), events, and [`mock_cache.json`](data/synthetic/mock_cache.json)
- [`tests/`](tests/) — Backend, trust/security, and Streamlit multipage UI tests
- [`docs/`](docs/) — [`ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`TRUST_AND_SECURITY.md`](docs/TRUST_AND_SECURITY.md)

## Quickstart

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\python.exe -m streamlit run app.py
```
