---
name: Postmark template convention
description: Durable delivery and credential rules for contact-form email across client sites.
---

Every client site uses its own Postmark server for contact-form notifications. Configuration belongs in Django admin and includes the verified From address, recipients, message stream, and an encrypted Server API token.

**Why:** Form delivery should be ready in every duplicated site without copying client credentials or requiring code edits at launch.

**How to apply:** Keep Postmark disabled until the client-owned server and sender are ready. Never reuse a server token across clients. Re-enter the token if the deployment's Django `SECRET_KEY` changes.