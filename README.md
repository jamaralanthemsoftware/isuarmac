# ISU-ARMAC website (Django CMS 5)

The isu-armac.com rebuild: Django 5.2 LTS + Django CMS 5, using the approved redesign. Every page, blog
post and old URL from the WordPress site is carried over.

## Note for Joe: about this branch

This branch (`isu-armac-cms`) is a standalone project built before the client template existed. It is
**not** based on the template on `main`, and nothing on `main` was changed. Key differences:

| | This branch | Template on `main` |
| --- | --- | --- |
| Content editing | Django CMS 5 (page tree, editable content blocks, front-end editing) | Plain Django admin models |
| Settings | Single `config/settings.py`, environment-driven | `config/settings/` split per environment |
| Admin URL / auth | `/admin/`, Django login | `/admin/jamarallogin/`, Google SSO, axes, argon2 |
| Forms | `QuoteRequest` model plus email via Django `send_mail` | Leads plus Postmark, reCAPTCHA and Anthem CRM |
| Deploy files | None yet | Dockerfile, `.do/app.yaml.example`, CI |

Merging options: bring the template's security, integrations and DigitalOcean files into this
project, or add Django CMS to the template and move `site_core/`, `templates/` and `static/` across.

**Content is not in git.** Pages, posts and team members are built by `import_wordpress` from the live
WordPress site (see below), and the 173 MB of WordPress uploads go in `media/`. Production needs
Postgres plus DigitalOcean Spaces (or another persistent volume) for `media/`. Requires Python 3.12+.

## Run it locally

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
xattr -w com.dropbox.ignored 1 .venv
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver 8077
```

Edit pages at http://localhost:8077/?edit (log in first at /admin/).

## Rebuild content from WordPress

```bash
.venv/bin/python manage.py fetch_wordpress      # pages, posts, categories, media list -> import_cache/
.venv/bin/python manage.py fetch_seo            # live <title> and meta descriptions
.venv/bin/python manage.py import_wordpress --reset
.venv/bin/python manage.py download_images      # media/uploads/ (skips files already present)
```

`--reset` deletes every page, post, team member and redirect, then rebuilds them. **Don't run it once
editors have started working in the CMS**, because it would erase their changes.

## Where things live

| Path | What |
| --- | --- |
| `site_core/designed_pages.py` | Pages built from the redesign: home, contractor, hospital, industries, section hubs, forms, team, testimonials, Life & AD&D |
| `site_core/wp_clean.py` | Turns Elementor/WordPress HTML into clean content blocks and repairs leftover AI-writing artifacts |
| `site_core/content_fixes.json` | Spelling, wording and brand-name corrections applied on import (see `docs/proofreading-report.md`) |
| `site_core/cms_plugins.py`, `models.py` | Editable content blocks: Hero, Section, Stats band, Card grid, Image and text, Team, Testimonial, Latest posts, CTA band, Callout, Pill links, FAQ, Quote form |
| `site_core/navigation.py` | Main menu, footer links, phone numbers and address |
| `static/css/site.css` | All styles (mobile first) |
| `templates/` | Page templates: `home.html`, `landing.html` (full-width sections), `detail.html` (text + sidebar) |
| `docs/photo-prompts.md` | ChatGPT prompts for replacement photos |

## URLs

- CMS pages keep their WordPress paths, for example `/insurance-center/service/commercial-insurance/contractor-insurance/`.
- Blog posts keep their root-level URLs (`/post-slug/`). The blog index is `/blog/`.
- Old duplicate pages and the 18 legacy `/service/…` URLs redirect permanently (`Redirects` in the admin).
- Old image links `/wp-content/uploads/…` redirect to `/media/uploads/…`.

## Lead forms

Quote, contractor, hospital, benefits and contact forms save to **Quote requests** in the admin and email
`LEAD_NOTIFICATION_EMAILS` (default info@isu-armac.com). Set `EMAIL_HOST`, `EMAIL_HOST_USER` and
`EMAIL_HOST_PASSWORD` in production. Without them, emails print to the console.

## Production settings (environment variables)

`DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`,
`DATABASE_URL` (Postgres), the email settings above, and persistent storage for `media/`.
