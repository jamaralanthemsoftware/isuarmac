# Django CMS template

A reusable, client-agnostic Django foundation for building and refining independently hosted client websites.

## Run & Operate

- `uv run --with-requirements requirements.txt python manage.py check` — validate the Django project
- `uv run --with-requirements requirements.txt python manage.py migrate` — apply local database migrations
- `uv run --with-requirements requirements.txt python manage.py runserver 0.0.0.0:${PORT:-8000}` — run locally
- The Replit preview workflow uses `config.settings.preview` and Gunicorn on port 8000.
- Local and preview work can use SQLite; production requires the environment variables documented in `README.md`.

## Stack

- Python 3.13
- Django 5.2
- SQLite for local/preview work; PostgreSQL for production
- Django templates and static CSS
- Gunicorn and WhiteNoise
- Optional DigitalOcean App Platform, Spaces, and Google admin SSO integrations
- Admin-configured Postmark form-notification delivery

## Where things live

- `config/settings/` — environment-specific Django settings
- `core/` — models, views, admin, forms, authentication, and migrations
- `templates/` — neutral frontend templates to replace for each client
- `static/css/site.css` — starter site styling
- `FRONTEND_IMPLEMENTATION_GUIDE.md` — frontend handoff and completion requirements
- `CLIENT_SETUP_CHECKLIST.md` — per-client launch checklist
- `PREVIEW_SETUP.md` — client-review preview setup

## Architecture decisions

- Keep this repository vendor- and client-agnostic; never copy client credentials, identifiers, data, media, or provider resources into it.
- Create each client site from this template in its own repository, database, hosting app, and environment configuration.
- Client repositories do not automatically inherit template changes; selectively port reviewed fixes and improvements.
- Production settings fail explicitly when required launch configuration is missing.
- Every client site uses its own Postmark server. Configure its verified sender, recipients, message stream, and encrypted Server API token in Django admin.
- GA4 and Search Console use a dedicated service OAuth flow with PKCE and encrypted refresh-token storage; never merge it with administrator Google SSO.
- Anthem CRM delivery uses each client's encrypted CMS-managed webhook, remains disabled by default, and never retries uncertain deliveries automatically.

## Product

The template provides admin-managed site identity, pages, services, FAQs, contact leads, downloadable files, SEO metadata, sitemaps, health checks, hardened administrator access, and neutral frontend templates ready for client-specific design.

## User preferences

- Use this project as the long-term master template for refining the basis of future Django client sites.

## Gotchas

- Do not use strict production settings for temporary client review; use `config.settings.preview`.
- Do not commit `.env`, SQLite databases, generated static files, or local media.
- Do not run migrations in every production web process; use a single pre-deploy migration job.
- Keep emergency administrator credentials in deployment secrets or a password manager, never in the repository.
