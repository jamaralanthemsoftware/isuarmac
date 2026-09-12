# Production performance and privacy checklist

This template keeps performance features reusable and client-neutral. Client projects may
replace the visual design, but should retain the safety boundaries below.

## Images

Use the `responsive_image` inclusion tag for uploaded CMS images:

```django
{% load performance_tags %}
{% responsive_image page.open_graph_image "Article cover" lcp=True sizes="(min-width: 900px) 60vw, 100vw" %}
```

The tag stores bounded Pillow renditions in the configured Django storage, emits WebP
`srcset` candidates, and always includes numeric intrinsic `width` and `height` values.
Use `lcp=True` for the one above-the-fold LCP image only. Images below the fold remain
lazy-loaded. Source uploads are capped at 25 million pixels and renditions at 2,000 pixels
wide. Every rendition key includes a digest of the source content, so replacing an upload
under the same filename creates a new URL while old content remains safely addressable.
The terminal candidate is always the source width (up to 2,000px), so a 900px image emits
320/640/900 candidates rather than upscaling a 640px candidate.

## Client-owned fonts

Do not add Google Fonts or other copyrighted font files to this repository. A client may
place a properly licensed WOFF2 file at `static/fonts/<family>-<weight>.woff2`, then add
its `@font-face` rule to the client stylesheet:

```css
@font-face {
  font-family: "Client Sans";
  src: url("../fonts/client-sans-400.woff2") format("woff2");
  font-style: normal;
  font-weight: 400;
  font-display: swap;
}
```

Preload only the one or two fonts needed by the first viewport by overriding the
`preload_fonts` block:

```django
{% block preload_fonts %}
  <link rel="preload" href="{% static 'fonts/client-sans-400.woff2' %}"
        as="font" type="font/woff2" crossorigin>
{% endblock %}
```

## CSS and third-party services

`static/css/site.css` is served through WhiteNoise's compressed manifest storage, so its
URL remains fingerprinted in production. Keep the small `critical_css` block limited to
layout needed before the stylesheet arrives. Do not replace the normal stylesheet with
JavaScript-dependent asynchronous CSS patterns: pages must remain styled when JavaScript is
disabled.

Maps, booking widgets, chat, and other providers belong in a page's
`third_party_scripts` block (or an explicitly selected component), never in `base.html`'s
global script list. Configure `THIRD_PARTY_SCRIPT_ORIGINS` as a comma-separated list of
client-approved HTTPS origins before using the helper. It rejects HTTP, `data:`,
`javascript:`, credential-bearing, and unapproved URLs, then adds `defer` and a service
marker. reCAPTCHA remains contact-form-only.

`PublicPageCacheMiddleware` is directly after `SecurityMiddleware`; this lets it apply
headers after downstream Session, CSRF, authentication, and Message middleware have
finished response processing. It never adds shared caching to admin, account, emergency
login, authenticated, cookie-bearing, session-modifying, message-setting, CSRF-setting,
error, POST, or restrictive-response requests. WhiteNoise static responses retain their
own immutable policy.

GA4 is emitted only when a measurement ID is configured. Set
`ANALYTICS_CONSENT_REQUIRED=true` when the client requires opt-in consent; the site's
consent UI should set the `analytics_consent=granted` cookie and dispatch
`analytics-consent-granted`. With consent not required, GA4 initializes immediately.
Initialization is guarded against duplicate loads.

The analytics component registers its consent event listener before checking the current
cookie, so a consent banner can grant consent at any time after the page starts. The
listener is one-shot and the loader has a second duplicate-initialization guard.

## Edge and web-server configuration

- [ ] Enable Brotli for text and SVG responses where the hosting platform supports it.
- [ ] Keep gzip enabled as a fallback for clients without Brotli.
- [ ] Verify compressed responses are sent with `Content-Encoding` and correct `Vary`.
- [ ] Disable Cloudflare Email Address Obfuscation unless the client explicitly needs it;
      it can rewrite visible addresses and interfere with exact HTML/content checks.
- [ ] Confirm HTTPS redirects before increasing `SECURE_HSTS_SECONDS`; then enable HSTS
      for subdomains and consider preload only after every subdomain is HTTPS-ready.
- [ ] Keep WhiteNoise immutable static caching enabled; do not replace manifest URLs with
      hand-written cache-busting query strings.

## PageSpeed verification

Run Lighthouse or PageSpeed Insights against the same production URL before and after
the performance work. Record mobile and desktop scores, LCP, CLS, INP, transfer size,
font count, and third-party request count. Test once with JavaScript disabled and once
with analytics consent denied/granted. A score change is not a substitute for checking
image dimensions, keyboard access, forms, and analytics behavior.