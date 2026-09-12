# Django Client Site Template

A reusable, backend-first Django foundation for independently hosted client websites.
Each client receives its own GitHub repository, PostgreSQL database, DigitalOcean App,
environment configuration, and content records.

This template is intentionally vendor- and client-agnostic. An existing client project may
be consulted for reusable patterns, but its code, database, media, domains, account IDs,
credentials, analytics identifiers, and service configuration must never be copied here.

## What is included

- Environment-specific settings for local development, client review, builds, and production
- Django admin-managed site identity, pages, services, leads, and downloadable files
- SEO fields, sitemap, robots.txt, and a production health endpoint
- PostgreSQL support through `DATABASE_URL`
- WhiteNoise static-file serving
- Optional DigitalOcean Spaces media storage
- Docker and DigitalOcean App Platform examples
- GitHub Actions checks
- Idempotent environment-driven admin provisioning
- Consistent administrator access at `/admin/jamarallogin/`
- Google administrator SSO restricted to pre-existing allowlisted staff users
- Rate-limited emergency login with Argon2 hashing and 14-character password minimum
- Admin-configured Google reCAPTCHA v3 with encrypted secret storage and a `0.80` default score
- Admin-configured Postmark form delivery with encrypted Server API token storage
- Admin-configured Anthem CRM webhook delivery with encrypted destination storage
- Dedicated GA4 and Search Console OAuth scaffolding with PKCE and encrypted refresh tokens
- Deliberately neutral templates that can be replaced per client

## Admin-managed integrations

The template includes the reusable connection and configuration layer for services commonly
needed on client websites. Client credentials and identifiers are deliberately excluded from
the repository and must be created separately for every duplicated site.

| Integration | Included in the template | Per-client launch work |
| --- | --- | --- |
| Google reCAPTCHA v3 | Contact-form token generation and server-side action, score, and hostname verification | Enter the site key, encrypted secret, and permanent hostnames in Django admin, then enable it |
| Postmark | Contact-form notifications, encrypted Server API token storage, From address, recipients, and message stream settings | Create a client-owned Postmark server, verify the sender, enter its settings in Django admin, and send a production test |
| Anthem CRM | Native Django lead delivery to the CRM's Gravity Forms-compatible webhook, encrypted webhook storage, and per-lead delivery status | Enter the client-specific webhook in Django admin, enable it, and confirm a controlled submission appears once in the CRM |
| Google Analytics 4 and Search Console | Separate service OAuth flow with PKCE, one-time state validation, required-scope checks, offline access, and encrypted refresh-token storage | Register the permanent-domain callback and OAuth secrets; property creation and verification are completed for the client implementation |
| Google administrator SSO | Allowlisted Google login for existing Django staff accounts | Register the separate administrator callback, provide OAuth secrets, and enable SSO |

The GA4/Search Console authorization and Google administrator login are intentionally separate.
Service-management scopes must never be added to the staff-login OAuth flow.

## Local setup

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

Replit does not require a virtual environment. Run:

```bash
cd django-client-site-template
python manage.py migrate
python manage.py runserver 0.0.0.0:${PORT:-8000}
```

Then create one **Site settings** record at the configured admin URL.

## Start a new client project

1. Keep this repository free of client branding and mark it as a **Template repository**
   in GitHub settings.
2. Select **Use this template** and create a new private repository for the client.
3. Follow `FRONTEND_IMPLEMENTATION_GUIDE.md` to replace the README title and neutral
   front-end files in `templates/` and `static/`.
4. Copy `.env.example` to `.env` locally. Never commit `.env`.
5. Run migrations and create the first admin.
6. Enter identity, contact, legal, analytics, pages, and services in Django admin.
7. Follow `PREVIEW_SETUP.md` to share and revise the site before launch integrations exist.
8. When preparing to go live, copy `.do/app.yaml.example` to `.do/app.yaml`, replace every
   placeholder, and commit it.
9. Create a DigitalOcean PostgreSQL database and inject its private `DATABASE_URL`.
10. If editors upload files, create a Spaces bucket and configure the `AWS_*` variables.
11. Import the repository into DigitalOcean App Platform and verify the first deployment
    before enabling normal deploy-on-push.
12. Complete `CLIENT_SETUP_CHECKLIST.md` before launch.

## Pre-launch client review

Use `config.settings.preview` while collaborating with the client before the final domain
and integrated services are ready. Preview mode supports local admin access, database-backed
contact leads, and local media without requiring SMTP, Google OAuth, Spaces, analytics,
webhooks, or PostgreSQL.

See `PREVIEW_SETUP.md` for the Replit settings, run command, persistence limitations, and
the exact transition to production. Do not use the strict production settings for this
stage: their missing-integration failures are intentional launch safeguards.

## Frontend implementation

`FRONTEND_IMPLEMENTATION_GUIDE.md` is the frontend handoff for each client build. It maps the
Django templates and context variables, defines responsive and accessibility expectations,
covers SEO, assets, performance, and third-party scripts, and includes a frontend completion
checklist. Use it before replacing the neutral starter design.

## Google reCAPTCHA v3

The public contact form includes a reusable reCAPTCHA v3 integration that is disabled by
default. Configure it only after the permanent domain is known:

1. Create a reCAPTCHA v3 key pair for the client's permanent domain in Google.
2. Sign in at `https://CLIENT-DOMAIN/admin/jamarallogin/`.
3. Open **reCAPTCHA integration** and enter the public site key, secret key, and allowed
   permanent hostnames.
4. Keep the minimum score at the template default of `0.80` unless reviewed traffic provides
   a reason to adjust it.
5. Enable the integration and submit a real contact-form test from the permanent domain.

The secret key is encrypted before it is stored in the database and is never sent to the
browser. Encryption is derived from the deployment's Django `SECRET_KEY`, so that value must
remain stable. If `SECRET_KEY` is rotated, re-enter the reCAPTCHA secret in Django admin.
Never copy a reCAPTCHA key pair between client domains.

## Production variables

Required:

- `DJANGO_SETTINGS_MODULE=config.settings.production`
- `SECRET_KEY`
- `DATABASE_URL`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `SITE_URL`

Recommended:

- `REQUIRE_POSTGRES=true`
- DigitalOcean Spaces variables when uploads are enabled
- `SECURE_HSTS_SECONDS=3600` initially; raise after HTTPS is confirmed

Contact submissions are always saved as Leads. Postmark notification delivery is configured
from Django admin and remains disabled until each client site's verified sender, recipients,
message stream, and Server API token are entered.

## Postmark form delivery

Every client website uses its own Postmark server for contact-form notifications:

1. Create a Postmark server for the client and verify its sending domain or sender signature.
2. Sign in at `https://CLIENT-DOMAIN/admin/jamarallogin/`.
3. Open **Postmark integration**.
4. Enter the verified **From email**, one or more recipient addresses, the message stream, and
   the Postmark **Server API token**.
5. Enable the integration and submit a production contact-form test.

The Server API token is encrypted before it is stored in the database and is never included in
templates or logs. Encryption is derived from the deployment's Django `SECRET_KEY`; if that key
is rotated, re-enter the Postmark token in Django admin. A delivery failure does not discard the
Lead—the submission remains available in Django admin and the visitor receives a warning.

## Google Analytics 4 and Search Console authorization

Django admin includes a shared OAuth connection scaffold for GA4 and Google Search Console.
It is intentionally separate from Google administrator sign-in and uses PKCE, one-time OAuth
state validation, offline access, and an encrypted refresh token.

For each permanent client domain:

1. Create or select the Google Cloud OAuth web client used for site-service authorization.
2. Enable the **Google Analytics Admin API**, **Search Console API**, and
   **Site Verification API**.
3. Add the exact authorized redirect URI:
   `https://CLIENT-DOMAIN/integrations/google/callback/`
4. Store `GOOGLE_SERVICES_OAUTH_CLIENT_ID`, `GOOGLE_SERVICES_OAUTH_CLIENT_SECRET`, and a
   dedicated Fernet `GOOGLE_SERVICES_ENCRYPTION_KEY` in deployment secrets.
5. Set `GOOGLE_SERVICES_CALLBACK_URI` to that exact HTTPS callback.
6. In Django admin, open **Google Analytics and Search Console** and connect the Google account
   that will manage the client's properties.

The authorization requests the scopes needed for future GA4 administration, Search Console
management, and HTML-tag site verification. GA4 property/data-stream provisioning and Search
Console verification are deliberately not automated in the master template; those actions
will be added and tested against the first client site that uses this scaffold.

## Anthem CRM form delivery

The native Django contact form can send saved Leads to Anthem CRM through its existing
Gravity Forms-compatible webhook endpoint. This replaces the previous WordPress-to-CRM path
without requiring WordPress or Gravity Forms. First name and last name are collected as
separate required form fields and sent separately to the CRM; names are not parsed from a
single combined field.

For each client site:

1. Obtain that client's Anthem CRM webhook URL.
2. Sign in at `https://CLIENT-DOMAIN/admin/jamarallogin/`.
3. Open **Anthem CRM integration**.
4. Enter the webhook URL. It is encrypted before database storage and is not displayed again.
5. Enable delivery and submit one controlled production form.
6. Confirm the Lead shows **Confirmed** in Django admin and appears once in Anthem CRM.

The integration is disabled by default and makes no CRM request until an administrator enters
a valid `live.anthemcrm.com` webhook and enables it. Every submission is saved as a Django Lead
before delivery is attempted. Confirmed, uncertain, and configuration-error states are recorded
on the Lead. Timeouts and uncertain responses are never retried automatically because the CRM
may have accepted the record before the response was interrupted.

## External services

External-service configuration belongs to the client project, not this template. Every new
site must receive new provider resources and identifiers:

- A new Postmark server, message stream, Server API token, and sender-domain verification
- A client-specific Anthem CRM webhook if CRM delivery is required
- New Google Analytics, Tag Manager, Search Console, Maps, and reCAPTCHA credentials as used
- A new DigitalOcean App, PostgreSQL database, Spaces bucket, and scoped access credentials
- New OAuth applications, webhook secrets, callback URLs, and API keys for any added service

Do not copy a previous client's `.env`, DigitalOcean app specification, database dump,
media bucket, OAuth application, or provider dashboard settings. Start from `.env.example`
and fill only the values issued for the new client. See `CLIENT_SETUP_CHECKLIST.md`.

## Hardened administrator login

Normal administrator access can use Google OAuth while Django continues to own staff status,
groups, and permissions. Google login is deliberately limited to an explicit email allowlist
and an existing active Django staff user. OAuth never creates a new staff account.

For each client:

1. Create the administrator in Django with `is_staff` enabled.
2. Create a new Google OAuth **Web application** for that client.
3. Add this authorized redirect URI:
   `https://CLIENT-DOMAIN/accounts/google/login/callback/`
4. Set `ENABLE_GOOGLE_ADMIN_SSO=true`.
5. Store `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` in the deployment secrets.
6. Set `ADMIN_GOOGLE_ALLOWED_EMAILS` to a comma-separated list of approved staff emails.
7. Keep `ADMIN_URL=admin/jamarallogin/` so the normal login is always available at
   `https://CLIENT-DOMAIN/admin/jamarallogin/`. Set a unique
   `ADMIN_LOCAL_LOGIN_URL` path for the client's emergency login.
8. Require two-step verification on every approved Google account.

The normal admin login URL redirects to Google when SSO is enabled. The separately configured
local login URL is reserved for the break-glass superuser. It is protected by five-attempt
lockout, a 30-minute cooldown, Argon2 password hashing, and the 14-character password policy.
Store that account's long random password in a password manager and deployment secret storage.

The template uses `/admin/jamarallogin/` consistently instead of Django's standard `/admin/`
path. The allowlist, existing-staff requirement, MFA, lockout, and emergency-account
discipline remain the primary security controls.

## Production commands

- Build: the Dockerfile installs dependencies and collects static files.
- Pre-deploy: `python manage.py migrate --noinput`
- Run: Gunicorn is defined by the Dockerfile.
- Health check: `/healthz/`

Do not run migrations in every web process. The provided App Platform example uses a
single pre-deploy job so multiple web instances cannot race.

## Admin provisioning

For automation, the template defaults the administrator username and email to
`jamaral@anthemsoftware.com`. Set the password as a secure environment secret:

- `DJANGO_SUPERUSER_PASSWORD`

Then run:

```bash
python manage.py provision_admin
```

The username and email can be overridden with `DJANGO_SUPERUSER_USERNAME` and
`DJANGO_SUPERUSER_EMAIL`. Existing users are not modified, so repeated startup is safe.
Secrets are not embedded in the repository and must be configured securely in every new
environment created from the template.

## Template maintenance

Treat this repository as a product with tagged releases. Client repositories should not
automatically pull template changes. Review and selectively port security fixes or new
features into each client project so client-specific code is never overwritten.

The original reference project remains independent. Template work must not edit, push to,
deploy, or migrate that project's repository or infrastructure.
