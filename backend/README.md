# Project Zim — Backend

Foundation-phase Django backend. No domain features (Accounts, etc.)
are implemented yet — this is intentionally just the skeleton the
rest of the platform will be built on.

## Stack

- Django 6.1
- Django REST Framework 3.18
- PostgreSQL
- Environment-variable configuration via `python-decouple`

## Project layout

```
backend/
  config/
    settings/
      base.py          # shared settings, all values env-driven
      development.py    # local overrides
      production.py     # hardened, fails fast if misconfigured
    urls.py              # mounts /admin/ and /api/v1/
    wsgi.py / asgi.py
  api/
    v1/
      urls.py            # aggregates each app's urls.py under /api/v1/
  apps/
    core/                # foundation-only: health check, no domain logic
  requirements/
    base.txt
    development.txt
    production.txt
  manage.py
  .env.example
```

Feature apps (starting with Accounts) will be added under `apps/` in
later phases, each with its own `urls.py` included from
`api/v1/urls.py`.

## Local setup

1. **Create and activate a virtual environment**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements/development.txt
   ```

3. **Configure environment variables**

   ```bash
   cp .env.example .env
   # edit .env with a real DJANGO_SECRET_KEY and your local DB credentials
   ```

4. **Create the PostgreSQL database**

   ```bash
   createuser projectzim --pwprompt
   createdb projectzim --owner=projectzim
   ```

5. **Run migrations**

   ```bash
   python manage.py migrate
   ```

6. **Run the development server**

   ```bash
   python manage.py runserver
   ```

7. **Verify the foundation is healthy**

   ```
   GET /api/v1/core/health/
   ```

   Returns `{"status": "ok", "database": true}` when the API process
   and the database are both reachable. This endpoint is unauthenticated
   by design — everything else under `/api/v1/` requires authentication
   by default.

## Running tests

```bash
python manage.py test
```

## Running checks

```bash
python manage.py check
```

## Settings modules

- Local development uses `config.settings.development` (the default
  in `manage.py`).
- `wsgi.py`/`asgi.py` default to `config.settings.production` for real
  deployments. Production **requires** `DJANGO_ALLOWED_HOSTS` to be
  set and will refuse to start without it.

## Notes for future phases

- Add each new feature app under `apps/`, and include its `urls.py`
  from `api/v1/urls.py` — do not add endpoint logic directly to
  `api/v1/urls.py` or `config/urls.py`.
- `apps.core` is reserved for cross-cutting foundation concerns
  (health checks now; may later hold shared base models/utilities).
  It should not accumulate feature-specific logic.
