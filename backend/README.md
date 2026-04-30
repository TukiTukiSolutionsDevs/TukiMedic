# Tuki-Medic Backend

FastAPI backend for the Tuki-Medic clinical platform.

## Prerequisites

- Python 3.12+
- PostgreSQL with the `pgvector` extension
- Redis
- Tesseract OCR + Poppler (`brew install tesseract poppler`)
- [Poetry](https://python-poetry.org/) for dependency management

## Quick start

```sh
cd backend
poetry install
cp .env.example .env
# Fill in .env — see required secrets below
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload
```

## Required secrets

### `SECRET_KEY`

JWT signing secret. Minimum 32 characters, high entropy. The app refuses to
boot with placeholder values.

```sh
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### `VAULT_MASTER_KEY`

AES-256-GCM master key for encrypting provider API keys at rest (S4.0.c).
Must be a **base64-encoded 32-byte** value. The app **fails at startup** if
this variable is absent or malformed.

Generate:

```sh
python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
```

Add to `.env`:

```
VAULT_MASTER_KEY=<output from above>
```

> **Security**: Never commit this value to version control. Rotating the
> master key requires re-creating all stored credentials — decrypt with the
> old key, re-encrypt with the new one before deploying.

## Running tests

```sh
cd backend
poetry run pytest
```

Tests set `VAULT_MASTER_KEY` (and `SECRET_KEY`) automatically via
`tests/conftest.py` — no `.env` needed for the test suite.
