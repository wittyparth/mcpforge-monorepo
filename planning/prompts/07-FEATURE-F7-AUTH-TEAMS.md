# 07 — Feature 7: Auth, Teams, Billing (Parallel Wave 1)

> **When to use:** After Wave 0 lands. Can run in parallel with F1, F2, F4, F5 (mostly independent).
> **Largest feature.** Combines auth hardening, GitHub OAuth, teams, API keys, Stripe billing.
> **Estimated time:** 10-14 days for one agent.

```
═══════════════════════════════════════════════════════════════════════
READ FIRST (in this exact order):
═══════════════════════════════════════════════════════════════════════

1. .planning/INDEX.md
2. .planning/CURRENT-STATE.md
3. .planning/00-MASTER-PLAN.md
4. .planning/09-INFRA-MIGRATIONS.md
5. AGENTS.md
6. .planning/features/08-FEATURE-AUTH-TEAMS-MANAGEMENT.md (your
   full spec — read in full)
7. apps/api/app/api/v1/endpoints/auth.py (existing register/
   login/refresh/logout/me — you'll extend)
8. apps/api/app/core/security.py (Wave 0 output — you use the
   Argon2id + refresh token rotation)
9. apps/api/app/models/user.py (existing — you'll extend with
   stripe_customer_id, etc.)
10. apps/api/alembic/versions/0005_add_teams.py (from Skeleton)
11. apps/api/alembic/versions/0006_add_api_keys.py (from Skeleton)
12. apps/api/alembic/versions/0007_add_billing.py (from Skeleton)
13. apps/web/src/app/(auth)/ for existing auth pages
14. apps/web/src/stores/auth-store.ts (existing Zustand auth
    store)

═══════════════════════════════════════════════════════════════════════
YOUR ASSIGNMENT
═══════════════════════════════════════════════════════════════════════

Feature: F7 — Auth Hardening + Teams + API Keys + Billing
Feature plan: .planning/features/08-FEATURE-AUTH-TEAMS-MANAGEMENT.md
Build order: Parallel Wave 1 (with F1, F2, F4, F5) OR after F4
              (if you need F4's deploy endpoints to gate on
              billing state).
Prerequisites: Wave 0 must be merged. Migrations 0005, 0006,
              0007 must be applied.

═══════════════════════════════════════════════════════════════════════
DELIVERABLES (this is the largest feature)
═══════════════════════════════════════════════════════════════════════

D1. **Email verification flow** (resend integration):
    - app/services/auth/email_verification.py
    - app/api/v1/endpoints/auth.py: POST /verify-email
    - Generate signed token, send via Resend
    - Tests: 4+ tests

D2. **Forgot/reset password flow**:
    - app/services/auth/password_reset.py
    - app/api/v1/endpoints/auth.py: POST /forgot-password,
      POST /reset-password
    - Tests: 4+ tests

D3. **GitHub OAuth**:
    - app/services/auth/oauth_github.py
    - app/api/v1/endpoints/auth.py: GET /github, GET /github/callback
    - State param for CSRF, code exchange, user upsert
    - Tests: 6+ tests

D4. **Team service**:
    - app/services/team_service.py (CRUD, invites, roles)
    - app/repositories/team_repo.py
    - 15+ tests

D5. **Team endpoints:**
    - app/api/v1/endpoints/team.py
    - GET /team, POST /team, POST /team/invite, POST /team/accept
    - PATCH /team/members/{id}, DELETE /team/members/{id}
    - GET /team/audit-log
    - 8+ tests

D6. **API keys service**:
    - app/services/api_key_service.py
    - app/repositories/api_key_repo.py
    - 8+ tests

D7. **API keys endpoints:**
    - app/api/v1/endpoints/api_keys.py
    - GET /api-keys, POST /api-keys, DELETE /api-keys/{id}
    - 6+ tests

D8. **Stripe billing**:
    - app/services/billing/stripe_client.py
    - app/services/billing/webhook_handler.py
    - app/services/billing/subscription_sync.py
    - app/repositories/billing_repo.py
    - 10+ tests (using stripe-mock or mocked SDK)

D9. **Billing endpoints:**
    - app/api/v1/endpoints/billing.py
    - GET /billing/plans, POST /billing/checkout
    - POST /billing/portal
    - POST /billing/webhook (signature-verified, no auth)
    - 8+ tests

D10. **Server management endpoints** (admin/management):
    - POST /api/v1/servers/{id}/duplicate
    - GET /api/v1/servers/{id}/versions
    - POST /api/v1/servers/{id}/rollback
    - 6+ tests

D11. **Update auth_service to integrate with billing:**
    - On user register: create Stripe customer (if not
      `STRIPE_LITIGATED_MODE=true`)
    - On subscription update: update user.plan
    - On subscription cancel: downgrade to free at period end

D12. **Wire team ownership to mcp_servers:**
    - Update mcp_servers to have team_id (from migration 0005)
    - Update create_server to optionally accept team_id
    - Update get_server / list_servers to filter by team
    - Permission check via team_service.check_permission

D13. **Rate limits by plan:**
    - Update F4's rate limiter to use user's plan from
      subscription, not from users.plan
    - Free: 60/hr 500/mo
    - Pro: 1000/hr 10000/mo
    - Team: 10000/hr 100000/mo

D14. **Update F4 gateway admin endpoints:**
    - Deploy: check subscription not past_due before allowing
    - Create: check plan limit (e.g., free tier = 2 servers max)

D15. **Frontend pages:**
    - /forgot-password
    - /reset-password?token=...
    - /verify-email?token=...
    - /dashboard/team
    - /dashboard/team/invite
    - /dashboard/team/accept?token=...
    - /dashboard/billing

D16. **Frontend components:**
    - forgot-password-form, reset-password-form
    - verify-email-banner
    - github-oauth-button
    - team-info-card, members-table, invite-form,
      role-selector, audit-log-table, remove-member-dialog
    - api-keys-table, create-key-dialog, key-display-once
    - plan-cards, current-plan-banner, checkout-button,
      invoice-history, cancel-subscription-dialog
    - duplicate-server-dialog, versions-tab, rollback-dialog

D17. **Frontend hooks:**
    - useForgotPassword, useResetPassword, useVerifyEmail
    - useGitHubOAuth
    - useTeam, useInvite, useUpdateMember, useRemoveMember,
      useAuditLog
    - useApiKeys, useCreateApiKey, useRevokeApiKey
    - usePlans, useCurrentSubscription, useCheckout, usePortal,
      useInvoices
    - useDuplicateServer, useVersions, useRollback

D18. **Tests:** ≥50 backend tests, ≥15 Vitest, 3 Playwright
    (team workflow, api-key flow, billing flow)

═══════════════════════════════════════════════════════════════════════
BUILD SEQUENCE (split this into 4 sub-phases for the agent)
═══════════════════════════════════════════════════════════════════════

Sub-phase A: Email + password (3 days)
  1. Email service abstraction (Resend client)
  2. Email verification service
  3. Password reset service
  4. Update auth endpoints
  5. Frontend forgot/reset/verify pages
  6. Tests

Sub-phase B: GitHub OAuth (2 days)
  7. OAuth service with state, code exchange
  8. Update auth endpoints
  9. Frontend GitHub button
  10. Tests

Sub-phase C: Teams (4 days)
  11. Team model + repository + service
  12. Team endpoints
  13. Wire mcp_servers.team_id
  14. Update server service to use team permissions
  15. Frontend team pages
  16. Tests

Sub-phase D: API keys (2 days)
  17. API key model + service
  18. API key endpoints
  19. Frontend API key management
  20. Tests

Sub-phase E: Billing (3 days)
  21. Stripe client wrapper
  22. Subscription + invoice models
  23. Webhook handler
  24. Billing endpoints
  25. Frontend billing pages
  26. Wire subscription → user.plan
  27. Wire plan limits (server count, call rate, AI credits)
  28. Tests

Sub-phase F: Server management (1 day)
  29. Duplicate, versions, rollback endpoints
  30. Frontend components
  31. Tests

═══════════════════════════════════════════════════════════════════════
DEFINITION OF DONE
═══════════════════════════════════════════════════════════════════════

[All from master template] Plus F7-specific:
[ ] Email verification works end-to-end (real Resend API key)
[ ] Forgot/reset password works
[ ] GitHub OAuth works (test with real GitHub OAuth app in dev)
[ ] Teams CRUD + invites + roles work
[ ] Audit log captures team events
[ ] Server duplicate/versions/rollback work
[ ] API keys with scopes work
[ ] Stripe checkout works (use Stripe test mode)
[ ] Stripe webhook is idempotent and signature-verified
[ ] Free/Pro/Team plans enforced
[ ] Email delivery via Resend works
[ ] 50+ backend tests
[ ] Playwright: full signup → verify → create team → invite →
    join → build server → deploy

═══════════════════════════════════════════════════════════════════════
REPORT BACK
═══════════════════════════════════════════════════════════════════════

[Standard format]

Plus F7-specific:
## Sub-phases completed: A/B/C/D/E/F
## Stripe test mode: yes/no
## Email delivery tested: yes/no
## GitHub OAuth tested: yes/no
```

---

## Reviewer's checklist

1. **End-to-end with Stripe test mode** — subscribe, verify webhook fires, verify user.plan updates, verify downgrades work.
2. **End-to-end team workflow** — invite, accept, role change, remove.
3. **Free tier limits enforced** — try to create a 3rd server on free, should fail.
4. **Email delivery** — register with real email, verify email arrives (use a real Resend API key in dev).
5. **API key auth** — create a key, use it via `Authorization: Bearer mcpforge_live_...`, verify it works.
6. **Refresh token rotation** still works (Wave 0 didn't break it).
