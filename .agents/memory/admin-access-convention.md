---
name: Admin access convention
description: Fixed normal administrator URL required across sites created from this template.
---

Every site created from this template uses `/admin/jamarallogin/` as its normal Django administrator login URL.

**Why:** The user wants one consistent administrator URL across every duplicated site rather than a different normal admin path per client.

**How to apply:** Preserve this default when refining the template or creating a client site. Emergency access may still use a unique path per client.