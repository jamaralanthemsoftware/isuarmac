---
name: reCAPTCHA template convention
description: Durable configuration and security rules for reCAPTCHA in sites created from this template.
---

Google reCAPTCHA v3 is disabled by default, uses a minimum score of `0.80`, and is configured from Django admin after the permanent domain is known. Its secret is encrypted at rest using the deployment's stable Django `SECRET_KEY`.

**Why:** The template must be safe to duplicate without carrying client credentials, while still being ready to complete from Django admin at launch.

**How to apply:** Give every client its own key pair and hostname allowlist. Never seed keys in the repository. Re-enter the encrypted reCAPTCHA secret if the Django `SECRET_KEY` changes.