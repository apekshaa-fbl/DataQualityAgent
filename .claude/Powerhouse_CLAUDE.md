# Powerhouse — agent guide

Firmable's internal control plane. FastAPI backend + React/Vite frontend, deployed as one Railway service. Services so far: Spotfix, Stageguard, Bees, Brigade, Spiders, Phonegrid, Atlas (soon).

---

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios. Trust internal code; validate only at boundaries (user input, external APIs).
- No comments unless the *why* is non-obvious (hidden constraint, subtle invariant, workaround).
- If you write 200 lines and it could be 50, rewrite it.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.
- Remove imports/variables/functions that YOUR changes made unused.

Test: every changed line traces directly to the user's request.

## 4. Goal-Driven Execution

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

## 5. Don't push or commit unless asked

Only run `git commit` / `git push` when the user explicitly asks. Never `--no-verify`. Never amend or force-push. If a hook fails, fix the root cause and create a NEW commit.

---

# Stack

**Backend** (`backend/`, Python 3.12)
- FastAPI 0.115 + Pydantic v2
- Supabase Python SDK (postgrest) — primary DB
- boto3 — DynamoDB (companies, people, regionals, registers)
- python-jose — JWT verify
- pytest + ruff + mypy

**Frontend** (`frontend/`)
- React 18 + Vite + TypeScript
- TanStack Query 5, react-hook-form + zod
- Tailwind (CSS vars in `--*` tokens), lucide-react, sonner toasts
- react-router-dom 6, cmdk, Radix primitives

# Layout

```
backend/app/
  main.py            FastAPI factory + middleware + router registration
  config.py          Settings (pydantic-settings) — read via get_settings()
  auth.py            current_user dep — Supabase JWT (ES256/HS256) + dev X-Actor-Email
  authz.py           require_admin / require_approver / require_phonegrid_user
  deps.py            @lru_cache singletons: supabase_client, dynamo repos, audit_logger
  domain/            Pydantic models (audit.Actor, company_core, person, regional, ...)
  repositories/      Dynamo + S3 wrappers
  routers/           ONE router per service: spotfix, bees, brigade, spiders, stageguard,
                     phonegrid, companies, people, regionals, lookups, enums, auth, users, audit
  services/          Cross-router business logic
  spotfix/service.py SpotFix queue + role checks (has_config_role, has_role_or_admin)
  security/          Headers, CSRF middleware
  tests/unit/        Pure logic (mock Supabase with MagicMock chains)
  tests/integration/ Router tests via FastAPI TestClient

frontend/src/
  App.tsx            Route table — one Route group per service
  components/
    Layout.tsx       Header nav: service tab + sub-nav per section (STAGEGUARD_NAV, BRIGADE_NAV, ...)
    HeaderSearch.tsx Spotfix-only ID search
    RequireRole.tsx  Loading-safe role gate
    fields/          Reusable form inputs (CountryCombobox, EnumSelect, LocationsTable)
  pages/
    Hub.tsx          Top-level service grid
    <service>/       One folder per service. <service>/Layout.tsx wraps shared sub-nav.
  lib/
    api.ts           Single fetch wrapper — CSRF, test-mode header, 401 refresh
    auth.ts          login/logout/refresh/fetchMe
    me.ts            useMe() / useCanAdmin() — TanStack-cached role data
    <service>.ts     Per-service API client (e.g. spiders.ts: spiders.create/list/get/download)
    types.ts         Shared TS domain types
```

---

# Backend conventions

## Routers — one per service

```python
router = APIRouter(prefix="/spiders/batches", tags=["spiders"])

_TABLE = "social_payloads"
_SCHEMA = "atomic"

def _t(client: Client) -> Any:
    return client.schema(_SCHEMA).table(_TABLE)

@router.get("", response_model=list[BatchSummary])
def list_my_batches(
    actor: Annotated[Actor, Depends(current_user)],
    client: Annotated[Client, Depends(supabase_client)],
) -> list[BatchSummary]:
    ...
```

Register in `app/main.py` under `create_app()`:

```python
from app.routers.spiders import router as spiders_router
app.include_router(spiders_router, prefix="/api")
```

## Auth & authz

- `Depends(current_user)` → authentication only. Returns `Actor(id: UUID, email: str)`.
- `Depends(require_admin)` / `require_approver` / `require_phonegrid_user` → authn + role check via `app.spotfix.service.has_role_or_admin`. **Admin is a superuser** — passes every role gate.
- Roles live in `app.roles` table (Supabase, schema `app`): `type ∈ {admin, approver, phonegrid_user}`, keyed by `identifier` (email).

## Pydantic models

- All request/response bodies are `BaseModel` with explicit `Literal[...]` enums, `Field(min_length=...)` bounds, and `field_validator` where input needs cleaning (strip whitespace, null bytes).
- Use `response_model=None` for endpoints returning raw `Response`/`StreamingResponse` — otherwise FastAPI tries to validate the body.

## Supabase patterns

- Always schema-qualify: `client.schema("app").table("roles")` — never bare `.from_()`.
- Paginate above 1000 rows (Supabase REST default page is 1000).
- Catch `postgrest.exceptions.APIError`; map `PGRST205` (table not found) to a 503 with a descriptive message.
- Background inserts: capture rows, return `202` with a synthesised batch id, then `BackgroundTasks` chunk-inserts so the request returns fast.

## Settings & secrets

`app.config.Settings` is the single source. Read via `get_settings()` (cached). Env vars live in `backend/.env` for local dev. Never read `os.environ` directly inside routers.

## Tests

- Markers: unit tests mock Supabase with `MagicMock` chains; integration tests use FastAPI `TestClient`.
- `POWERHOUSE_TEST_MODE=1` swaps `current_user` for a fixed `e2e@firmable.com` actor and uses in-memory repos.
- Always include the negative path (403 / 401 / 404) alongside the happy path.
- Run: `make test` or `cd backend && pytest tests/`.

---

# Frontend conventions

## Routes

- One `<Route>` block per service in `App.tsx`. Sub-routes use a section `<Layout>` element for shared sub-nav.
- Default redirect at the service root: `/spiders` → `/spiders/linkedin-fetch/batches` (`<Navigate replace />`).

## Header nav

`components/Layout.tsx` shows a service-tab nav based on URL prefix. Update both the `*_NAV` array and the `*_PREFIXES` set when adding a service. Empty `*_NAV` → header tabs stay hidden; use the in-page tab pattern instead.

## Data fetching

- Always go through `lib/api.ts` (`api.get/post/put/delete`) — never raw `fetch` except in `lib/auth.ts`.
- One service file per backend service (`lib/spiders.ts`, `lib/spotfix.ts`, ...). Export a small object with typed methods.
- TanStack Query keys: `['<service>-<resource>', ...params]`. `staleTime: 60_000` for cacheable reads. Invalidate keys on mutation.

## Role gates

```tsx
const canAdmin = useCanAdmin();          // boolean, false while loading
const { data: me, isLoading } = useMe(); // when you need the loading state
<RequireRole role="approver"><Button .../></RequireRole>
```

## Styling

- Tailwind utility classes + CSS variables: `var(--surface)`, `var(--surface-2)`, `var(--surface-solid)`, `var(--text)`, `var(--text-muted)`, `var(--text-dim)`, `var(--border)`, `var(--border-strong)`, `var(--accent-grad)`, `var(--people-grad)`, `var(--company-grad)`, `var(--regional-grad)`, `var(--hero-grad)`.
- Buttons: `.btn-gradient` (primary), `.btn-secondary`. Pills: `.pill .pill-info|positive|negative|warning|neutral`.
- Cards: `.card` + `p-*`. Match the visual rhythm of nearby pages — don't introduce one-off design.

## Forms

- `react-hook-form` + `zod` resolver.
- Read-only fields when value is server-derived (`fqdn`, `acn`).
- Toast on success/error with `sonner`.

---

# Local dev

```bash
make install   # backend venv + npm install
make dev       # uvicorn :8000 + vite :5173
make test      # pytest + vitest
make lint      # ruff + eslint
make typecheck # mypy + tsc -b
```

Frontend dev server proxies `/api/*` to `:8000`. Login at `/login` with any Supabase user.

For E2E without auth: `VITE_TEST_MODE=1` (frontend) + `POWERHOUSE_TEST_MODE=1` (backend) — auth is bypassed via `X-Actor-Email`, default `e2e@firmable.com`. Never set these in deployed envs.

---

# Deploy (Railway, single service)

Root `Dockerfile` builds the React app and serves it from the same FastAPI container.
- One Railway service, one domain.
- Public port `8080`.
- Env: Supabase + AWS/Dynamo from `backend/.env`.
- Optional `VITE_API_URL` build arg — leave empty for same-origin.

After deploy:
1. `https://<domain>/` — UI
2. `https://<domain>/health` — `{"status":"ok"}`
3. `/login` → Supabase user → app

---

# Skills

Skills live in `.claude/skills/<name>/SKILL.md`.

**Repo-local skills:**

- **`add-service`** — scaffold a brand-new top-level service (Hub card + router + frontend section). Use when adding something like Spotfix/Bees/Brigade/Spiders.
- **`api-spec-generator`** — incremental endpoints on an existing router (request/response models + tests + Logfire + Bearer auth). Use when adding a single endpoint to an existing service.
- **`ui-design`** — Powerhouse UI design patterns (navigation, hub cards, sub-nav pills, bulk-upload parse-before-submit, list/empty/error states, color tokens). Codified from the Firmable web frontend so new UI doesn't drift. Use when adding any new page, tab, or upload flow.

**Globally-installed skills already in scope (use these — don't duplicate):**

- `verify` / `superpowers:verification-before-completion` — run the app and confirm a change works before claiming done.
- `superpowers:brainstorming` — required before any creative or new-feature work.
- `superpowers:test-driven-development` — required before writing implementation code.
- `superpowers:systematic-debugging` — before proposing any bug fix.
- `code-review` / `simplify` — diff review and cleanup.
- `anthropic-skills:skill-creator` / `superpowers:writing-skills` — when creating new skills.

Invoke with `/<skill-name>` or via the `Skill` tool. Before authoring a new skill, check this list to avoid duplication.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
