# Feature 7 — Authentication, Teams, Server Management & Billing

> **PRD reference:** § 7 Feature 7 (lines 519-548)
> **Build order:** Wave 3 (v1.0 launch) + Wave 0 (security hardening bits)
> **Estimated effort:** 10-14 days for one engineer (largest feature)

---

## 0. TL;DR

The biggest, most complex feature. Includes: (1) hardening the existing auth flow, (2) adding GitHub OAuth, (3) team collaboration (invites, roles, audit logs), (4) server management polish (duplicate, version history, rollback, pause), (5) API keys for programmatic access, (6) Stripe billing (Pro $12/mo, Team $29/seat/mo). Most of this is a "make it production-grade" pass on what the PRD specifies.

This feature ships in v1.0 (Wave 3). Some hardening bits (Argon2id, refresh token rotation, CSRF) ship in Wave 0 as part of the security foundation.

---

## 1. Goals & Non-Goals

### 1.1 In scope (Wave 0 — security hardening, ships first)
- Migrate password hashing bcrypt → Argon2id
- HaveIBeenPwned k-anonymity check on register
- Account lockout (5 failed logins → 15-min lockout)
- Refresh token rotation tracking in Redis (jti claim)
- CSRF protection (double-submit cookie pattern)
- Auth required on all gateway routes (already done in F4)

### 1.2 In scope (Wave 3)
- Email verification flow (Resend integration)
- Forgot/reset password flows
- GitHub OAuth (state, code exchange, user upsert)
- Teams: create, invite, roles (admin/editor/viewer), audit log
- Server management: duplicate, version history (last 10), rollback, pause/resume
- API keys (5 max, scoped, SHA-256 hash)
- Stripe billing: Pro $12/mo, Team $29/seat/mo, free tier limits

### 1.3 Out of scope
- SSO/SAML (v2.0)
- Custom roles (v2.0)
- Webhook subscriptions (v1.1)
- Usage-based pricing tiers (v1.1)

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Authentication flows                                    │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────┐    │
│  │ Email/Pwd  │  │ GitHub     │  │ Email verify      │    │
│  │ Argon2id   │  │ OAuth 2.0  │  │ Token (signed)   │    │
│  │ + HIBP     │  │ + state    │  │                  │    │
│  └────────────┘  └────────────┘  └──────────────────┘    │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  Authorization                                           │
│  • Resource owner check: user owns server OR             │
│    user is in team that owns server                      │
│  • Role check: admin can do anything, editor can edit    │
│    but not delete/billing, viewer is read-only           │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  Teams                                                   │
│  • 1 team per Pro/Team plan (initially)                  │
│  • Owner = user who created team                         │
│  • Members: admin/editor/viewer                          │
│  • Invitations: 48h expiry, email + token                │
│  • Audit log: every action, 90-day retention             │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  API Keys (programmatic)                                 │
│  • Format: mcpforge_live_<32 base62 chars>                │
│  • Stored as SHA-256 hash, plaintext shown once           │
│  • Scopes: servers:read, servers:write, analytics:read   │
│  • 5 max per user                                        │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  Billing (Stripe)                                        │
│  • Customer: 1:1 with user (Pro) or team owner (Team)     │
│  • Subscription: 1 per customer                          │
│  • Webhook: idempotent, signature-verified                │
│  • Free tier: 2 servers, 500 calls/mo, 3 AI credits/mo  │
│  • Pro: $12/mo, 10 servers, 10K calls/mo, unlimited AI   │
│  • Team: $29/seat/mo (min 2), unlimited servers, 100K/mo │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Backend Changes

### 3.1 Migration `0008_add_refresh_token_tracking.py` (Wave 0)

```python
"""add refresh token rotation tracking (or use Redis only)"""
# Decision: use Redis only. Faster, auto-expires. No migration needed.
# This is just a note in the plan.
```

### 3.2 Migration `0005_add_teams.py` (Wave 3)

```python
"""add teams, team_memberships, team_invitations, audit_logs"""
# (Per 09-INFRA-MIGRATIONS.md § 2.4)
# Also: ALTER mcp_servers ADD team_id, owner_user_id
```

### 3.3 Migration `0006_add_api_keys.py` (Wave 3)

```python
"""add api_keys"""
# (Per 09-INFRA-MIGRATIONS.md § 2.5)
```

### 3.4 Migration `0007_add_billing.py` (Wave 3)

```python
"""add subscriptions, invoices; add stripe_customer_id to users"""
# (Per 09-INFRA-MIGRATIONS.md § 2.6)
```

### 3.5 New files (Wave 0)

```
app/services/auth/
├── password.py                   # Argon2id, HIBP, lockout (NEW)
├── token_rotation.py             # jti tracking, reuse detection (NEW)
└── csrf.py                       # double-submit cookie middleware (NEW)

app/core/
├── middleware/
│   ├── csrf.py                   # CSRF middleware (NEW)
│   └── rate_limit.py             # per-IP rate limit (NEW)
```

### 3.6 New files (Wave 3)

```
app/services/auth/
├── email_verification.py         # Generate token, send via Resend (NEW)
├── password_reset.py             # Forgot/reset password (NEW)
└── oauth_github.py               # GitHub OAuth flow (NEW)

app/services/
├── team_service.py               # Team CRUD, invites, roles (NEW)
├── api_key_service.py            # API key CRUD (NEW)
└── billing/
    ├── __init__.py
    ├── stripe_client.py          # Stripe wrapper (NEW)
    ├── webhook_handler.py        # Webhook events (NEW)
    └── subscription_sync.py      # Keep DB in sync with Stripe (NEW)

app/api/v1/endpoints/
├── team.py                       # /team, /team/invite, etc. (NEW)
├── api_keys.py                   # /api-keys/* (NEW)
└── billing.py                    # /billing/* (NEW)

app/models/
├── team.py                       # Team, TeamMembership, TeamInvitation (NEW)
├── audit_log.py                  # AuditLog (NEW)
├── api_key.py                    # ApiKey (NEW)
└── billing.py                    # Subscription, Invoice (NEW)

app/schemas/
├── team.py
├── api_key.py
└── billing.py

tests/
├── test_auth_hardening.py        # 12 tests
├── test_team_service.py          # 15 tests
├── test_api_key_service.py       # 8 tests
├── test_billing.py               # 10 tests
└── test_e2e_auth.py              # 8 tests
```

### 3.7 Wave 0: Password hardening (Argon2id + HIBP + lockout)

```python
# app/services/auth/password.py
from passlib.context import CryptContext
import httpx

pwd_context = CryptContext(
    schemes=["argon2"],
    argon2__memory_cost=65536,  # 64MB
    argon2__time_cost=3,
    argon2__parallelism=4,
    deprecated="auto",
)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

async def check_hibp_breached(password: str) -> bool:
    """Check if password is in HaveIBeenPwned via k-anonymity API."""
    sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.pwnedpasswords.com/range/{prefix}")
        response.raise_for_status()
    
    for line in response.text.splitlines():
        hash_suffix, count = line.split(":")
        if hash_suffix == suffix:
            return int(count) > 0
    return False

class AccountLockout:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def is_locked(self, email: str) -> bool:
        count = await self.redis.get(f"login_fails:{email}")
        if count and int(count) >= 5:
            ttl = await self.redis.ttl(f"login_fails:{email}")
            if ttl > 0:
                return True
        return False
    
    async def record_failure(self, email: str) -> None:
        await self.redis.incr(f"login_fails:{email}")
        await self.redis.expire(f"login_fails:{email}", 900)  # 15 min
    
    async def record_success(self, email: str) -> None:
        await self.redis.delete(f"login_fails:{email}")
```

### 3.8 Wave 0: CSRF protection (double-submit cookie)

```python
# app/core/middleware/csrf.py
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

class CSRFMiddleware(BaseHTTPMiddleware):
    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
    EXEMPT_PATHS = {"/api/v1/auth/refresh"}  # uses cookie auth, not body
    
    async def dispatch(self, request: Request, call_next):
        if request.method in self.SAFE_METHODS or request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)
        
        # Check Origin or Referer header
        origin = request.headers.get("Origin") or request.headers.get("Referer", "").rstrip("/")
        if not origin:
            raise HTTPException(403, "Missing Origin header")
        
        # Origin must match CORS_ORIGINS
        if origin not in settings.CORS_ORIGINS:
            raise HTTPException(403, f"Origin {origin} not allowed")
        
        # For cookie auth, also check X-CSRF-Token header matches csrf_token cookie
        cookie_token = request.cookies.get("csrf_token")
        header_token = request.headers.get("X-CSRF-Token")
        if cookie_token and header_token != cookie_token:
            raise HTTPException(403, "CSRF token mismatch")
        
        return await call_next(request)
```

CSRF token is set in cookie on login (or first visit) and rotated on every state-changing request.

### 3.9 Wave 0: Refresh token rotation

```python
# app/services/auth/token_rotation.py
import uuid

def generate_jti() -> str:
    return str(uuid.uuid4())

async def is_jti_revoked(jti: str) -> bool:
    r = await get_redis()
    return await r.exists(f"revoked_jti:{jti}")

async def revoke_jti(jti: str, ttl_seconds: int) -> None:
    r = await get_redis()
    await r.setex(f"revoked_jti:{jti}", ttl_seconds, "1")

# In auth_service.refresh():
async def refresh(self, refresh_token: str):
    payload = decode_refresh_token(refresh_token)
    jti = payload.get("jti")
    user_id = payload["sub"]
    
    if await is_jti_revoked(jti):
        # Reuse detected — invalidate ALL tokens for this user
        await self._revoke_all_user_tokens(user_id)
        raise UnauthorizedError("Token reuse detected — all sessions invalidated")
    
    # Mark this jti as used (single-use)
    await revoke_jti(jti, ttl_seconds=7 * 86400)
    
    # Issue new pair
    return generate_token_pair(user_id)
```

### 3.10 Wave 3: GitHub OAuth

```python
# app/services/auth/oauth_github.py
import httpx

class GitHubOAuth:
    AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USER_URL = "https://api.github.com/user"
    
    async def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": settings.GITHUB_OAUTH_CLIENT_ID,
            "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
            "scope": "user:email",
            "state": state,
        }
        return f"{self.AUTHORIZE_URL}?" + urlencode(params)
    
    async def exchange_code(self, code: str, state: str) -> dict:
        # 1. Verify state (CSRF)
        # 2. Exchange code for access token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                json={
                    "client_id": settings.GITHUB_OAUTH_CLIENT_ID,
                    "client_secret": settings.GITHUB_OAUTH_CLIENT_SECRET,
                    "code": code,
                },
                headers={"Accept": "application/json"},
            )
            data = response.json()
            github_token = data["access_token"]
            
            # 3. Get user info
            user_response = await client.get(
                self.USER_URL,
                headers={"Authorization": f"Bearer {github_token}"},
            )
            github_user = user_response.json()
        
        return github_user  # contains id, login, email, name, avatar_url
    
    async def upsert_user(self, github_user: dict) -> User:
        async with async_session_factory() as session:
            repo = UserRepository(session)
            # Try to find by github_id
            user = await repo.get_by_github_id(str(github_user["id"]))
            if user:
                # Update last login
                return await repo.update(user, last_login_at=datetime.utcnow())
            # Try to find by email
            user = await repo.get_by_email(github_user["email"])
            if user:
                # Link GitHub to existing account
                return await repo.update(user, github_id=str(github_user["id"]))
            # Create new user
            return await repo.create(
                email=github_user["email"],
                password_hash=None,  # OAuth-only
                display_name=github_user.get("name") or github_user["login"],
                avatar_url=github_user.get("avatar_url"),
                github_id=str(github_user["id"]),
                email_verified=True,  # GitHub has verified
            )
```

### 3.11 Wave 3: Team service

```python
# app/services/team_service.py
class TeamService:
    async def create_team(self, owner_id: UUID, name: str) -> Team:
        async with async_session_factory() as session:
            team = Team(name=name, owner_id=owner_id)
            session.add(team)
            # Owner is automatically an admin
            membership = TeamMembership(team_id=team.id, user_id=owner_id, role="admin")
            session.add(membership)
            await session.commit()
            return team
    
    async def invite_member(self, team_id: UUID, inviter_id: UUID, email: str, role: str) -> TeamInvitation:
        # 1. Verify inviter is admin
        # 2. Check team member count < plan limit
        # 3. Generate token
        token = secrets.token_urlsafe(32)
        # 4. Create invitation
        invitation = TeamInvitation(
            team_id=team_id,
            email=email,
            role=role,
            token=token,
            invited_by=inviter_id,
            expires_at=datetime.utcnow() + timedelta(hours=48),
        )
        # 5. Send email with link
        await send_email(
            to=email,
            template="team_invitation",
            context={"team_name": team.name, "accept_url": f"{settings.APP_URL}/team/accept?token={token}"},
        )
        return invitation
    
    async def accept_invitation(self, token: str, user_id: UUID) -> TeamMembership:
        invitation = await self.repo.get_by_token(token)
        if not invitation or invitation.expires_at < datetime.utcnow():
            raise ValidationError("Invalid or expired invitation")
        if invitation.accepted_at:
            raise ValidationError("Invitation already accepted")
        
        membership = TeamMembership(
            team_id=invitation.team_id,
            user_id=user_id,
            role=invitation.role,
            invited_by=invitation.invited_by,
        )
        invitation.accepted_at = datetime.utcnow()
        await self.session.commit()
        return membership
    
    async def check_permission(self, user_id: UUID, team_id: UUID, required_role: str) -> bool:
        membership = await self.repo.get_membership(team_id, user_id)
        if not membership:
            return False
        role_hierarchy = {"viewer": 1, "editor": 2, "admin": 3}
        return role_hierarchy[membership.role] >= role_hierarchy[required_role]
```

### 3.12 Wave 3: API keys

```python
# app/services/api_key_service.py
import secrets
import hashlib

class ApiKeyService:
    PREFIX = "mcpforge_live_"
    
    async def create_key(self, user_id: UUID, name: str, scopes: list[str]) -> tuple[ApiKey, str]:
        # Generate plaintext
        plaintext = self.PREFIX + secrets.token_urlsafe(24)  # 32 chars
        
        # Hash for storage
        key_hash = hashlib.sha256(plaintext.encode()).hexdigest()
        key_prefix = plaintext[:12]  # "mcpforge_li"
        
        api_key = ApiKey(
            user_id=user_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=scopes,
        )
        self.session.add(api_key)
        await self.session.commit()
        
        return api_key, plaintext  # plaintext shown ONCE
    
    async def authenticate(self, plaintext: str) -> User | None:
        if not plaintext.startswith(self.PREFIX):
            return None
        key_hash = hashlib.sha256(plaintext.encode()).hexdigest()
        api_key = await self.repo.get_by_hash(key_hash)
        if not api_key or api_key.revoked_at:
            return None
        # Update last_used_at (async, non-blocking)
        await self.repo.touch(api_key.id)
        return await self.user_repo.get_by_id(api_key.user_id)
    
    async def check_scope(self, api_key: ApiKey, required_scope: str) -> bool:
        return required_scope in api_key.scopes or "admin" in api_key.scopes
```

API keys can be used in the `Authorization: Bearer mcpforge_live_xxx` header (alternative to JWT).

### 3.13 Wave 3: Stripe billing

```python
# app/services/billing/stripe_client.py
import stripe

class StripeClient:
    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY
    
    async def create_customer(self, user: User) -> str:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.display_name,
            metadata={"user_id": str(user.id)},
        )
        return customer.id
    
    async def create_subscription(self, customer_id: str, price_id: str, seat_count: int = 1) -> str:
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id, "quantity": seat_count}],
            payment_behavior="default_incomplete",
            payment_settings={"save_default_payment_method": "on_subscription"},
            expand=["latest_invoice.payment_intent"],
        )
        return subscription.id
    
    async def create_checkout_session(self, user: User, price_id: str, success_url: str, cancel_url: str) -> str:
        session = stripe.checkout.Session.create(
            customer_email=user.email,
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"user_id": str(user.id)},
        )
        return session.url
```

```python
# app/services/billing/webhook_handler.py
class WebhookHandler:
    async def handle(self, event: dict):
        event_type = event["type"]
        
        if event_type == "customer.subscription.created":
            await self._on_subscription_created(event["data"]["object"])
        elif event_type == "customer.subscription.updated":
            await self._on_subscription_updated(event["data"]["object"])
        elif event_type == "customer.subscription.deleted":
            await self._on_subscription_deleted(event["data"]["object"])
        elif event_type == "invoice.payment_succeeded":
            await self._on_payment_succeeded(event["data"]["object"])
        elif event_type == "invoice.payment_failed":
            await self._on_payment_failed(event["data"]["object"])
    
    async def _on_subscription_updated(self, subscription):
        async with async_session_factory() as session:
            sub = await SubscriptionRepository(session).get_by_stripe_id(subscription["id"])
            if sub:
                sub.status = subscription["status"]
                sub.current_period_end = datetime.fromtimestamp(subscription["current_period_end"])
                sub.cancel_at_period_end = subscription["cancel_at_period_end"]
                await session.commit()
            # Update user plan
            user = await UserRepository(session).get_by_id(sub.user_id)
            if user:
                plan = PLAN_FROM_PRICE[subscription["items"]["data"][0]["price"]["id"]]
                user.plan = plan
                await session.commit()
```

### 3.14 New endpoints (Wave 3)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/auth/forgot-password` | Send reset email |
| POST | `/api/v1/auth/reset-password` | Reset with token |
| POST | `/api/v1/auth/verify-email` | Verify with token |
| GET | `/api/v1/auth/github` | Start GitHub OAuth |
| GET | `/api/v1/auth/github/callback` | OAuth callback |
| GET | `/api/v1/team` | Get team info |
| POST | `/api/v1/team` | Create team |
| POST | `/api/v1/team/invite` | Invite member |
| POST | `/api/v1/team/accept` | Accept invitation |
| PATCH | `/api/v1/team/members/{id}` | Update role |
| DELETE | `/api/v1/team/members/{id}` | Remove member |
| GET | `/api/v1/team/audit-log` | Audit log (admin only) |
| GET | `/api/v1/api-keys` | List keys |
| POST | `/api/v1/api-keys` | Create key (returns plaintext once) |
| DELETE | `/api/v1/api-keys/{id}` | Revoke |
| GET | `/api/v1/billing/plans` | List plans |
| POST | `/api/v1/billing/checkout` | Create Stripe checkout session |
| POST | `/api/v1/billing/portal` | Create Stripe customer portal session |
| POST | `/api/v1/billing/webhook` | Stripe webhook (no auth, signature-verified) |
| POST | `/api/v1/servers/{id}/duplicate` | Duplicate server |
| GET | `/api/v1/servers/{id}/versions` | List versions |
| POST | `/api/v1/servers/{id}/rollback` | Rollback to version |

---

## 4. Frontend Changes

### 4.1 New pages

```
/forgot-password                       (NEW)
/reset-password?token=...             (NEW)
/verify-email?token=...               (NEW)
/auth/github                          (initiates OAuth)
/auth/github/callback                 (handles redirect)
/dashboard/team                       (NEW)
/dashboard/team/invite                (NEW)
/dashboard/team/accept?token=...      (NEW)
/dashboard/billing                    (NEW)
```

### 4.2 New components

```
src/components/auth/
├── forgot-password-form.tsx
├── reset-password-form.tsx
├── verify-email-banner.tsx
└── github-oauth-button.tsx

src/components/team/
├── team-info-card.tsx
├── members-table.tsx
├── invite-form.tsx
├── role-selector.tsx
├── audit-log-table.tsx
└── remove-member-dialog.tsx

src/components/billing/
├── plan-cards.tsx
├── current-plan-banner.tsx
├── checkout-button.tsx
├── invoice-history.tsx
└── cancel-subscription-dialog.tsx

src/components/api-keys/
├── api-keys-table.tsx
├── create-key-dialog.tsx
└── key-display-once.tsx                # Shown once, with copy

src/components/server/
├── duplicate-server-dialog.tsx
├── versions-tab.tsx
├── rollback-dialog.tsx
└── pause-resume-toggle.tsx              (from F4)
```

### 4.3 New hooks

```typescript
// src/hooks/use-auth.ts (extend)
export function useForgotPassword() { ... }
export function useResetPassword() { ... }
export function useVerifyEmail() { ... }
export function useGitHubOAuth() { ... }

// src/hooks/use-team.ts (NEW)
export function useTeam() { ... }
export function useInviteMember() { ... }
export function useUpdateMemberRole() { ... }
export function useRemoveMember() { ... }
export function useAuditLog() { ... }

// src/hooks/use-api-keys.ts (NEW)
export function useApiKeys() { ... }
export function useCreateApiKey() { ... }
export function useRevokeApiKey() { ... }

// src/hooks/use-billing.ts (NEW)
export function usePlans() { ... }
export function useCurrentSubscription() { ... }
export function useCheckout() { ... }
export function usePortal() { ... }
export function useInvoices() { ... }

// src/hooks/use-servers.ts (extend)
export function useDuplicateServer() { ... }
export function useVersions() { ... }
export function useRollback() { ... }
```

---

## 5. Database / Migration Plan

Migrations 0005, 0006, 0007, 0008 (per 09-INFRA-MIGRATIONS.md).

---

## 6. Environment Variables

| Var | Required? | Default | Notes |
|---|---|---|---|
| `GITHUB_OAUTH_CLIENT_ID` | No | (empty) | From GitHub OAuth app |
| `GITHUB_OAUTH_CLIENT_SECRET` | No | (empty) | |
| `GITHUB_OAUTH_REDIRECT_URI` | No | (auto) | `https://api.example.com/api/v1/auth/github/callback` |
| `EMAIL_PROVIDER_API_KEY` | No | (empty) | Resend API key |
| `EMAIL_FROM_ADDRESS` | No | `noreply@mcpforge.io` | Verified sender |
| `STRIPE_SECRET_KEY` | No | (empty) | `sk_test_...` or `sk_live_...` |
| `STRIPE_WEBHOOK_SECRET` | No | (empty) | `whsec_...` |
| `STRIPE_PRICE_PRO_MONTHLY` | No | (empty) | `price_...` |
| `STRIPE_PRICE_PRO_YEARLY` | No | (empty) | |
| `STRIPE_PRICE_TEAM_SEAT_MONTHLY` | No | (empty) | |
| `STRIPE_LITIGATED_MODE` | No | `false` | Skip Stripe entirely for testing |

Frontend:
- `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`
- `NEXT_PUBLIC_GITHUB_OAUTH_CLIENT_ID`

---

## 7. Observability

```python
logger.info("user_registered", user_id=user_id, via="email"|"github")
logger.info("user_login_success", user_id=user_id)
logger.warning("user_login_failed", email=email, reason=reason, attempt=count)
logger.warning("account_locked", email=email, locked_until=...)
logger.info("password_reset_requested", email=email)
logger.info("password_reset_completed", user_id=user_id)
logger.info("email_verified", user_id=user_id)
logger.info("team_created", team_id=team_id, owner_id=owner_id)
logger.info("team_member_invited", team_id=team_id, email=email, role=role, invited_by=inviter_id)
logger.info("team_member_accepted", team_id=team_id, user_id=user_id)
logger.info("team_member_removed", team_id=team_id, user_id=removed_id, removed_by=remover_id)
logger.info("api_key_created", user_id=user_id, key_id=key_id, name=name)
logger.info("api_key_revoked", user_id=user_id, key_id=key_id)
logger.info("subscription_created", user_id=user_id, plan=plan, stripe_sub_id=sub_id)
logger.info("subscription_cancelled", user_id=user_id, cancel_at=date)
logger.info("payment_succeeded", user_id=user_id, amount_cents=amount, invoice_id=invoice_id)
logger.warning("payment_failed", user_id=user_id, invoice_id=invoice_id, attempt=count)
```

Audit log for team events:
```python
audit_log = AuditLog(
    team_id=team_id,
    user_id=actor_id,
    action="server.delete",
    resource_type="server",
    resource_id=server_id,
    metadata={"reason": "user_initiated"},
    ip_address=request.client.host,
    user_agent=request.headers.get("user-agent"),
)
```

---

## 8. Edge Cases

| Case | Response |
|---|---|
| User tries to register with already-registered email | 409 Conflict |
| User uses weak password | 422 with HIBP warning |
| User attempts login with breached password | 422 (allow, but log warning) |
| 5 failed logins | 423 Locked, with retry-after |
| GitHub OAuth state mismatch | 400 Invalid state |
| GitHub OAuth code reuse | 400 Invalid code |
| Team member tries to delete server they're not admin of | 403 |
| Team invite email not registered | Invitation can be accepted after they register (use email match) |
| Team has 0 members after owner removes themselves | Prevented (must transfer ownership first) |
| API key with admin scope used for billing | Allowed (admin scope = all) |
| Stripe webhook signature invalid | 400 (don't process) |
| Stripe webhook duplicate (idempotent) | Detect via `event.id`, skip if already processed |
| User cancels Stripe sub | status → "canceled" at period end; downgrade at period end |
| User's card fails on renewal | 3-day grace, then downgrade to free |
| Plan limits exceeded (e.g., 3 servers on free with 4th) | 402 Payment Required, suggest upgrade |

---

## 9. Definition of Done

**Wave 0 (security hardening):**
- [ ] Passwords stored as Argon2id
- [ ] HIBP check on register
- [ ] Account lockout after 5 fails
- [ ] Refresh token rotation in Redis
- [ ] CSRF middleware applied
- [ ] All existing tests still pass

**Wave 3:**
- [ ] Email verification flow works end-to-end
- [ ] Forgot/reset password works
- [ ] GitHub OAuth works
- [ ] Teams CRUD + invites + roles
- [ ] Audit log captures team events
- [ ] Server duplicate/versions/rollback
- [ ] API keys with scopes
- [ ] Stripe checkout + webhook + customer portal
- [ ] Free/Pro/Team plans enforced
- [ ] Email delivery via Resend works
- [ ] Playwright E2E: full signup → verify → create team → invite → join → build server → deploy

---

## 10. Build Sequence (split across Wave 0 and Wave 3)

**Wave 0 (4-5 days):**
1. Argon2id migration + HIBP
2. Account lockout
3. Refresh token rotation
4. CSRF middleware
5. Tests for all

**Wave 3 (10-14 days):**
1. Migrations 0005, 0006, 0007
2. Models: Team, TeamMembership, TeamInvitation, AuditLog, ApiKey, Subscription, Invoice
3. Email service integration (Resend)
4. Email verification flow
5. Password reset flow
6. GitHub OAuth
7. Team service
8. Team endpoints
9. Server management endpoints (duplicate, versions, rollback)
10. API key service
11. API key endpoints
12. Stripe client wrapper
13. Stripe webhook handler
14. Billing endpoints
15. Frontend: forgot/reset/verify pages
16. Frontend: GitHub OAuth button
17. Frontend: team pages
18. Frontend: API key management
19. Frontend: billing pages
20. Frontend: server management UI
21. Tests for all
22. Playwright E2E: full team workflow
23. Manual: end-to-end with real Stripe test mode

---

*This is the largest and most complex feature. See `09-INFRA-MIGRATIONS.md` for the full migration specs.*
