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
- Reusable responsive WebP image tags, self-hosted font hooks, critical CSS, and safe public caching
- Consent-aware deferred GA4 and selective third-party script hooks
- Superuser-only WordPress WXR and same-origin sitemap blog importer

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

## WordPress blog importer

Superusers can open **Blog posts → Start another import** in Django admin. Choose either a
WordPress WXR export upload or a public Yoast, Rank Math, AIOSEO, or standard sitemap URL.
Every successful item is saved as an unpublished `BlogPost` draft; existing source URLs/GUIDs
are reported as duplicates and never overwritten. WXR content, title, slug, author, canonical
URL, source identifiers, original dates, metadata, and attachment relationships are retained.
For crawled pages, featured-image discovery uses Open Graph, Twitter cards, Article JSON-LD,
WordPress image markup, and then article images.

The importer rejects unsafe XML DTD/entity declarations, sanitizes HTML, blocks private,
reserved, link-local, and loopback addresses, revalidates DNS on redirects, and stays on the
original public origin. Responses, uploads, redirects, total bytes, sitemap items, and image
types/sizes are bounded. Media failures are recorded against the import item while preserving
the draft. Persistent run and item reports are available in admin. It is intentionally
synchronous and should be used in bounded batches; it does not execute JavaScript, authenticate
to a source site, infer arbitrary non-sitemap URLs, or publish automatically.

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

## Initialize post-live setup

Use this runbook **after the first production deployment is reachable at the permanent HTTPS
domain**. It is designed so the site owner can give a new project agent one instruction:

> **Initialize the go-live process.**

When that instruction is received, the agent must use this section and
`CLIENT_SETUP_CHECKLIST.md` to guide the owner through the stages below in order. The agent
should inspect the project first, report what is already complete, and ask only for the next
missing non-secret information. Secrets must be entered through DigitalOcean environment
variables or the masked Django admin fields—never pasted into chat, source code, GitHub, or
logs.

Do not enable an integration merely because credentials were entered. Complete its production
test and verification gate before proceeding to the next stage.

### Stage 1 — Confirm the production foundation

Required input:

- Permanent domain, including whether `www` redirects to the apex domain or the reverse
- DigitalOcean App Platform application and PostgreSQL database
- Whether the site accepts uploaded files and therefore requires DigitalOcean Spaces

Steps:

1. Confirm the permanent domain loads over HTTPS.
2. Confirm `/healthz/` returns `200`.
3. Confirm the production deployment uses:
   - `DJANGO_SETTINGS_MODULE=config.settings.production`
   - A unique, stable `SECRET_KEY`
   - The private production `DATABASE_URL`
   - Exact `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `SITE_URL` values
   - `REQUIRE_POSTGRES=true`
4. Run migrations and confirm there are no pending migrations.
5. Confirm static files and, when applicable, uploaded media load from production.
6. Sign in at `https://CLIENT-DOMAIN/admin/jamarallogin/`.
7. Confirm **Site settings**, public contact information, legal links, and production metadata.

Verification gate: the public site, Django admin, database, static assets, and health endpoint
must work on the permanent domain before configuring external services.

### Stage 2 — Activate Google reCAPTCHA v3

Required from Google reCAPTCHA:

- Production-domain **site key**
- Production-domain **secret key**
- Exact allowed hostname or hostnames

Steps:

1. Create a new reCAPTCHA v3 key pair for this client and permanent domain.
2. In Django admin, open **reCAPTCHA integration**.
3. Enter the site key, secret key, and allowed production hostnames.
4. Keep the minimum score at `0.80` unless there is a documented reason to change it.
5. Enable reCAPTCHA.
6. Submit a real production contact form and confirm the Lead is saved.
7. Confirm an invalid or missing token is rejected.

Verification gate: legitimate production submissions work and unverified submissions do not
create Leads. Never reuse another client's keys.

### Stage 3 — Activate Postmark form delivery

Required from a new client-owned Postmark server:

- Verified sending domain or sender signature
- Verified **From email**
- Notification recipient addresses
- Message stream, normally the transactional stream used for website forms
- **Server API token** for that Postmark server

The Server API token is the credential the application needs; a Postmark server name or
dashboard ID by itself cannot send email.

Steps:

1. Create a separate Postmark server for the client.
2. Complete sender-domain or sender-signature verification.
3. In Django admin, open **Postmark integration**.
4. Enter the From email, recipients, message stream, and masked Server API token.
5. Enable Postmark delivery.
6. Submit the production contact form.
7. Confirm the Lead remains in Django admin and the notification reaches every intended inbox.
8. Confirm Reply-To uses the visitor's email address.

Verification gate: one production submission creates one Lead and one expected Postmark
notification. Never reuse another client's server or Server API token.

### Stage 4 — Connect GA4 and Google Search Console

Required in the client's Google Cloud project:

- OAuth 2.0 **Web application** client ID and client secret dedicated to site services
- Enabled **Google Analytics Admin API**
- Enabled **Search Console API**
- Enabled **Site Verification API**
- Exact authorized redirect URI:
  `https://CLIENT-DOMAIN/integrations/google/callback/`
- A dedicated Fernet encryption key for refresh-token storage

Required DigitalOcean secrets:

- `GOOGLE_SERVICES_OAUTH_CLIENT_ID`
- `GOOGLE_SERVICES_OAUTH_CLIENT_SECRET`
- `GOOGLE_SERVICES_ENCRYPTION_KEY`
- `GOOGLE_SERVICES_CALLBACK_URI`

Steps:

1. Create or select the client-owned Google Cloud project.
2. Configure the OAuth consent screen and enable the three required APIs.
3. Create the site-services OAuth web client.
4. Register the exact callback above; do not use the administrator SSO callback.
5. Add the four values as DigitalOcean secrets and redeploy.
6. In Django admin, open **Google Analytics and Search Console**.
7. Connect the Google account that will manage the client's properties.
8. Create or select the client's GA4 property and production web data stream.
9. Add the resulting GA4 measurement ID to the site's analytics configuration.
10. Create and verify the production Search Console URL-prefix property.
11. Submit `https://CLIENT-DOMAIN/sitemap.xml` in Search Console.
12. Give the client appropriate access to both properties.

Verification gate: the OAuth connection is healthy, GA4 receives production traffic, the
Search Console property is verified, and the sitemap is accepted. GA4/GSC service OAuth must
remain separate from Google administrator SSO.

### Stage 5 — Activate Anthem CRM when applicable

First ask whether this client uses Anthem CRM. If not, leave the integration disabled and mark
this stage **not applicable**.

Required when applicable:

- Client-specific Anthem CRM Gravity Forms-compatible webhook URL

Steps:

1. Obtain the webhook for the correct Anthem CRM organization.
2. In Django admin, open **Anthem CRM integration**.
3. Enter the masked webhook URL and enable delivery.
4. Submit one controlled production form using separate first-name and last-name fields.
5. Confirm the Django Lead shows **Confirmed**.
6. Confirm exactly one corresponding prospect appears in Anthem CRM.

Verification gate: one submission creates one Lead and one CRM prospect. If the Lead shows
**Needs review**, check Anthem CRM manually before attempting anything again. Never
automatically retry an uncertain webhook delivery.

### Stage 6 — Final go-live verification

1. Test the complete contact flow once:
   - Separate required first-name and last-name fields
   - reCAPTCHA verification
   - Django Lead persistence
   - Postmark notification
   - Anthem CRM confirmation when applicable
2. Verify public pages, canonical production URLs, Open Graph metadata, `robots.txt`, and
   `sitemap.xml`.
3. Run `python manage.py check --deploy` with production settings.
4. Review production logs and confirm credentials, webhook URLs, form contents, and tokens are
   not logged.
5. Raise `SECURE_HSTS_SECONDS` only after HTTPS and redirects are confirmed.
6. Enable normal deploy-on-push only after the first production deployment and all applicable
   integration tests succeed.
7. Record which integrations are **complete**, **not applicable**, or **blocked**, without
   recording secret values.

The initialization is complete only when every applicable verification gate passes. The agent
must finish with an ordered status report showing completed stages, remaining owner actions,
and any blocked provider-side setup.

## Pre-launch client review

Use `config.settings.preview` while collaborating with the client before the final domain
and integrated services are ready. Preview mode supports local admin access, database-backed
contact leads, and local media without requiring SMTP, Google OAuth, Spaces, analytics,
webhooks, or PostgreSQL.

See `PREVIEW_SETUP.md` for the Replit settings, run command, persistence limitations, and
the exact transition to production. Do not use the strict production settings for this
stage: their missing-integration failures are intentional launch safeguards.

## Performance and privacy

`PERFORMANCE.md` documents the reusable responsive image tag, client-owned WOFF2 convention,
font preload hooks, critical CSS boundaries, selective third-party scripts, consent-aware
GA4 behavior, and production Brotli/gzip, Cloudflare, HSTS, and PageSpeed checks. Normal CSS
continues to use WhiteNoise's fingerprinted manifest storage.

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
- `ANALYTICS_CONSENT_REQUIRED=true` when the client requires analytics opt-in
- `THIRD_PARTY_SCRIPT_ORIGINS` as the explicit comma-separated allowlist for page-selective
  HTTPS maps, booking, or chat scripts
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
