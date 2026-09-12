# Pre-launch client review

Use preview mode while the site is being designed and reviewed with the client.

The template's reCAPTCHA integration remains disabled during temporary preview work. Configure
and enable it from Django admin only after the permanent domain and its reCAPTCHA v3 keys exist.
It intentionally does not require a custom domain, PostgreSQL, Spaces, SMTP,
Google OAuth, analytics, webhooks, or other launch-only services.

## Replit preview configuration

Set these environment values for the review site:

```text
DJANGO_SETTINGS_MODULE=config.settings.preview
SECRET_KEY=<a new long random value>
ALLOWED_HOSTS=<the Replit preview hostname>
CSRF_TRUSTED_ORIGINS=https://<the Replit preview hostname>
SITE_URL=https://<the Replit preview hostname>
ENABLE_GOOGLE_ADMIN_SSO=false
USE_SPACES=false
SERVE_LOCAL_MEDIA=true
```

Use the hostname only in `ALLOWED_HOSTS`; do not include `https://`. Include the
scheme in `CSRF_TRUSTED_ORIGINS` and `SITE_URL`.

Use this run command:

```bash
python manage.py migrate --noinput &&
python manage.py provision_admin &&
gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}
```

Create the first local administrator with `python manage.py createsuperuser`,
or temporarily set the three `DJANGO_SUPERUSER_*` variables and run:

```bash
python manage.py provision_admin
```

Use the configured `ADMIN_LOCAL_LOGIN_URL` to sign in. Google login remains off
until the client has a domain and a client-owned OAuth application.

## What works without integrations

- Pages, services, FAQs, navigation, SEO fields, and site settings
- Local administrator login
- Contact submissions, stored as Leads in Django admin
- Local uploaded media for the current review environment
- Static files, sitemap, robots.txt, and health checks

The contact form stores submissions in the database. The Postmark integration is disabled by
default, so preview does not send email unless an administrator deliberately configures and
enables it. Review leads in Django admin during preview.

## Persistence warning

SQLite and local media are appropriate for development and a single persistent
Replit workspace. They are not suitable for an ephemeral or multi-instance
deployment: redeploys may discard files, and separate migration jobs do not
share a SQLite filesystem with the web service.

If client-entered review content must survive rebuilds or the review site runs
as a deployment, provision PostgreSQL before collecting important content.
Provision Spaces before relying on uploaded files. These resources can still
use the temporary platform hostname; a custom domain, email, OAuth, analytics,
and webhooks can wait until launch.

The GA4 and Search Console admin dashboard is available in preview, but its Connect button
remains disabled until the separate Google services OAuth credentials, encryption key, and
exact callback URI are configured.

Anthem CRM delivery is also disabled by default. Preview contact submissions remain available
as Django Leads without contacting the CRM until a valid webhook is entered and enabled in
Django admin.

## Moving from preview to production

Before launch:

1. Switch to `config.settings.production`.
2. Provide PostgreSQL through `DATABASE_URL`.
3. Configure the final domain, HTTPS origins, and `SITE_URL`.
4. Configure persistent media storage if uploads are used.
5. Enter the client-specific Postmark settings in Django admin, enable delivery, and test it.
6. Create the client-owned Google OAuth application and staff allowlist if used.
7. Register the separate `/integrations/google/callback/` URI and connect GA4/Search Console.
8. Enter and test the client-specific Anthem CRM webhook if CRM delivery is required.
9. Add only the analytics, consent, maps, CAPTCHA, and other webhook services required.
10. Run the production checks in `CLIENT_SETUP_CHECKLIST.md`.

Do not copy credentials or service resources from the template or another client.