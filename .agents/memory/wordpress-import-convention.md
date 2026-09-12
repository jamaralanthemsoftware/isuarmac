---
name: WordPress import convention
description: Safety and lifecycle rules for WXR uploads and public sitemap-based WordPress migrations.
---

WordPress migrations support either WXR uploads or same-origin public sitemap crawling. Imports always create drafts, preserve reports, skip duplicates, and never overwrite or publish existing content.

**Why:** Sitemap-derived metadata and featured images can be inferred incorrectly, while hostile XML, HTML, redirects, DNS behavior, and media can expose the server or exhaust resources.

**How to apply:** Keep imports superuser-only; enforce aggregate limits, pinned public destinations, sanitized HTML, verified images, and human review before publication.