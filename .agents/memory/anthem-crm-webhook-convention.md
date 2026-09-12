---
name: Anthem CRM webhook convention
description: Durable safety and delivery rules for sending native Django form leads to Anthem CRM.
---

Native Django form leads use Anthem CRM's Gravity Forms-compatible webhook. The CMS-managed destination is encrypted, disabled by default, and delivery outcomes are stored on each Lead.

**Why:** A timeout can occur after the CRM accepts a prospect, so automatic retries could create duplicate CRM records. The local Lead must remain the source of recovery information.

**How to apply:** Require a controlled production test before enabling delivery. Treat uncertain results as manual-review cases and never retry them automatically.