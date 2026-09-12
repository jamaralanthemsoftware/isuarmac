---
name: Google services OAuth convention
description: Durable separation and security rules for GA4 and Search Console authorization.
---

GA4 and Search Console use a dedicated Django-admin OAuth flow with PKCE, one-time state validation, offline access, and an encrypted refresh token. It is separate from administrator Google SSO.

**Why:** Service-management permissions are broader and longer-lived than identity-login permissions. Combining the flows would unnecessarily broaden administrator sign-in and complicate callback security.

**How to apply:** Keep service OAuth credentials and callbacks separate from staff-login configuration. Add GA4/GSC provisioning actions only in client implementations that need them.