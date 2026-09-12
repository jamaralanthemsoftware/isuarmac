---
name: Performance convention
description: Reusable PageSpeed, caching, analytics, font, and responsive-image rules for client sites.
---

Public pages use conservative anonymous shared caching, content-versioned responsive WebP renditions, explicit image dimensions, LCP priority, deferred below-fold media, and consent-aware analytics.

**Why:** Client sites need repeatable performance gains without caching authenticated/session responses, serving stale replaced media, or loading third parties before consent.

**How to apply:** Use the shared image tags and template hooks, keep third-party origins allowlisted, self-host licensed fonts, and verify production behavior with the performance checklist.