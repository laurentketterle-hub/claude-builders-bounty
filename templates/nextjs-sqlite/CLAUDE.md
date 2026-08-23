# CLAUDE.md — Next.js 15 + SQLite SaaS

> Opinionated, production-ready engineering guide for building a SaaS product with
> **Next.js 15 (App Router)**, **React 19**, **TypeScript**, and **SQLite**
> (better-sqlite3 or Turso). Read this before writing any code. Every rule below
> states *why* it exists — when you deviate, you inherit the reason too.

---

## 1. Stack & versions (pinned, do not drift)

| Concern      | Choice                                  | Why |
|--------------|-----------------------------------------|-----|
| Framework    | Next.js 15, **App Router only**         | RSC + Server Actions give us server-first data flow; the Pages Router is legacy and its mental model fights our architecture. |
| Language     | TypeScript, `strict: true` (no `any` escaping lint) | SQLite schemas + Server Action payloads are the two places bugs live; strict typing is the only thing that catches them before production. |
| Runtime      | Node.js 22 LTS                          | `node:sqlite` is available, and Next.js 15's Turbopack is stable on 22. |
| Database     | **SQLite** via `better-sqlite3` (single node) **or** `@libsql/client` (Turso, multi-region) | One file, zero ops, transactional. We do *not* use an embedded ORM that hides SQL. |
| ORM / types  | **Drizzle ORM** + `drizzle-kit`         | Thin, zero-runtime-overhead mapping; migrations are plain SQL we can read and review. |
| Validation   | **Zod** (v3)                            | Single source of truth for every boundary: forms, Server Actions, API routes. |
| Auth         | **Auth.js (NextAuth v5)** or **Lucia** w/ SQLite adapter | Session-in-cookie, HTTP-only. Auth logic must never live in client components. |
| Styling      | **Tailwind CSS v4** + CSS variables     | Utility classes keep the UI layer boring; variables hold the design tokens. |
| Package mgr  | **pnpm** (with `workspace` if we split) | Deterministic, fast, and strict about undeclared deps via its symlinked `node_modules`. |

---

## 2. Folder structure

```text
.
├── app/                          # App Router routes — server-first
│   ├── (marketing)/              # Public pages (landing, pricing, blog)
│   ├── (auth)/                   # login / register / forgot-password
│   ├── (app)/                    # Authenticated workspace (the SaaS itself)
│   │   ├── layout.tsx            # Shell: sidebar + topbar + auth guard
│   │   ├── (dashboard)/page.tsx
│   │   └── settings/…
│   ├── api/                      # External callbacks only (webhooks)
│   │   └── webhooks/stripe/route.ts
│   ├── globals.css
│   ├── layout.tsx                # Root: fonts, metadata, providers
│   └── error.tsx / not-found.tsx
├── components/
│   ├── ui/                       # Primitives (button, input, dialog, table)
│   ├── forms/                    # Client form components (thin, "use client")
│   └── shared/                   # Logo, empty-state, page-header…
├── lib/
│   ├── db/
│   │   ├── index.ts              # Connection + Drizzle instance (WAL on)
│   │   ├── schema/               # One file per domain (users.ts, teams.ts, billing.ts)
│   │   └── migrations/           # Generated .sql files (committed)
│   ├── actions/                  # Server Actions — one file per domain, "use server"
│   ├── auth.ts                   # Auth.js config + session helper
│   ├── env.ts                    # zod-validated process.env (fail fast at boot)
│   └── utils/                    # Pure helpers (dates, money, slugs, ids)
├── drizzle.config.ts
├── middleware.ts                 # Route protection (auth redirect) — edge-safe
└── package.json
```

**Rules**
- **Route groups `(…)` define the auth boundary**, not a `useAuth()` hook sprinkled everywhere. A page inside `(app)` is authenticated *by construction*.
- `app/api/` is for **external callbacks only**. Internal mutations are Server Actions, never hand-rolled `fetch('/api/…')`.
- `lib/db/schema/` is **one file per domain**. A single giant `schema.ts` is a merge-conflict and review bottleneck.

---

## 3. Naming conventions

- **Files**: `kebab-case` (`team-actions.ts`, `billing-schema.ts`). Route folders match URLs, so also `kebab-case`.
- **Components**: `PascalCase` filename == component name (`UserMenu.tsx` → `export function UserMenu`).
- **DB tables/columns**: `snake_case` (`users`, `created_at`, `team_id`). Drizzle maps them to `camelCase` in TS — do not fight this.
- **Foreign keys**: `<singular>_id` (`team_id`, `owner_id`). Join tables `<a>_<b>` alphabetized (`team_user`, not `user_team`).
- **Server Actions**: verb-first (`createTeam`, `inviteMember`, `cancelSubscription`). Return value is a **discriminated result object**, never a thrown error.
- **Booleans**: `is_` / `has_` / `can_` prefix (`is_active`, `has_2fa`). Avoid double-negatives (`disabled`) in the DB — name the *desired* state.

---

## 4. SQLite & migration conventions

1. **WAL mode is mandatory, set on every connection**:
   ```sql
   PRAGMA journal_mode = WAL;
   PRAGMA synchronous = NORMAL;
   PRAGMA foreign_keys = ON;   -- SQLite has these OFF by default; we need them ON
   ```
   *Why:* WAL decouples readers from the single writer so a long read never blocks a write. `foreign_keys = ON` is per-connection and defaults OFF — forgetting it silently disables referential integrity.

2. **Schema lives in TypeScript (`lib/db/schema/`), migrations are generated SQL.** Never hand-write `CREATE TABLE` in a migration; change the schema, then `pnpm db:generate`. Migrations are **committed** and applied with `pnpm db:migrate` (a single transaction).

3. **Never edit a committed migration.** Forward-only. If a migration is wrong and unshipped, delete+regenerate; if shipped, write a *new* corrective migration.

4. **Always parameterize.** Use the Drizzle query builder (`db.select().from(users).where(eq(users.id, id))`). Never string-concatenate user input into SQL — this is the one rule with no exceptions.

5. **Declare `onDelete`/`onUpdate` explicitly** on every relation (`cascade` for owned rows, `restrict`/`set null` for shared references). "Default" is a landmine.

6. **Migrations must be reversible in thought, if not in practice:** when you add a `NOT NULL` column to a non-empty table, include a `DEFAULT` or backfill. A migration that fails on a customer DB is an outage.

---

## 5. Component patterns

### Server Components by default
- Everything in `app/` is a **React Server Component** unless it *must* be interactive. Fetch data directly with `await db.query…` — no `useEffect` + `fetch` loading spinners for data that exists at render time.

### Client components are islands
- `"use client";` is reserved for: event handlers, `useState`/`useEffect`, browser APIs (`localStorage`, `navigator`), or third-party client libs.
- Keep islands **leaf-level and small**. A form is a client island; its *submission logic* is a Server Action.

### Server Actions for all mutations
```ts
// lib/actions/team.actions.ts
"use server";

const CreateTeam = z.object({ name: z.string().min(2).max(60) });

export async function createTeam(input: unknown) {
  const parsed = CreateTeam.safeParse(input);
  if (!parsed.success) return { ok: false, error: parsed.error.flatten() };
  // …auth check, db write…
  revalidatePath("/app");
  return { ok: true, data: { id: team.id } };
}
```
- **Always `safeParse` at the boundary.** `input` is `unknown` — the browser is not your friend.
- **Return `{ ok, data | error }`**, never throw. The UI can then render errors without a try/catch.
- **Revalidate after every successful mutation** (`revalidatePath`/`revalidateTag`) so cached RSC data can't go stale.

### Loading & error states
- Use `loading.tsx` and `error.tsx` per route (App Router conventions) instead of hand-rolled spinners and per-component try/catch.

---

## 6. Development commands

```bash
pnpm install          # install (never npm/yarn — lockfile mismatch breaks CI)
pnpm dev              # next dev (Turbopack)
pnpm build            # next build — typecheck + lint run first
pnpm lint             # eslint
pnpm typecheck        # tsc --noEmit
pnpm db:generate      # drizzle-kit generate (schema → SQL migration)
pnpm db:migrate       # apply pending migrations
pnpm db:studio        # drizzle-kit studio (visual table inspector)
pnpm test             # vitest
```

---

## 7. What we DON'T do (and why)

| Anti-pattern | Why we avoid it | Do instead |
|---|---|---|
| ❌ Prisma / TypeORM / Knex | Heavy runtime, slow cold starts, opaque generated SQL, and a second query language to learn. SQLite's advantage is *simplicity* — a fat ORM erases it. | Drizzle ORM: SQL-first, typed, near-zero overhead. |
| ❌ `fetch` from the client to internal `/api` routes | Reintroduces client-server round trips, CORS/auth plumbing, and leaks the API surface. | Server Actions for internal mutations; `app/api/` only for *external* callbacks. |
| ❌ Raw `localStorage` / client-side JWT for auth | XSS can exfiltrate tokens; nothing revokes a stolen token client-side. | HTTP-only, `Secure`, `SameSite=Lax` cookies via Auth.js/Lucia. |
| ❌ `useEffect` data fetching | Waterfalls, flicker, duplicated cache logic, and hydration mismatches. | Server Components fetch at render; SWR/React Query *only* for client-triggered refetch. |
| ❌ Barrel files (`index.ts` re-exporting dozens of modules) | Kills tree-shaking and HMR, creates circular-import traps. | Direct imports (`import { Button } from "@/components/ui/button"`). |
| ❌ `any` in Server Action payloads or DB rows | The exact boundary where runtime type bugs and injection-adjacent mistakes occur. | Zod `safeParse` on `unknown`, strict Drizzle types. |
| ❌ `prisma migrate`-style "magic" migrations / down-migrations | SQLite has no transactional DDL across many statements; "down" migrations drift from reality. | Forward-only generated SQL, reviewed like any other code. |
| ❌ Storing currency as float, or dates as strings | Floating point corrupts money; string dates break range queries and sorting. | Money in **integer cents**, timestamps as `integer` Unix ms or ISO-8601 text (be consistent). |
| ❌ Env vars read directly (`process.env.X` scattered everywhere) | A typo in a key is a silent `undefined` that ships to prod. | `lib/env.ts` validates all env at boot with Zod and throws loudly. |

---

## 8. Definition of done (for any PR)

- [ ] `pnpm typecheck` and `pnpm lint` pass.
- [ ] Any schema change ships with a generated migration (forward-only, committed).
- [ ] Every Server Action validates input with Zod and returns `{ ok, … }`.
- [ ] Mutations call `revalidatePath`/`revalidateTag`.
- [ ] New auth-gated routes live inside `(app)/`, not behind a manual `if (!session)` check.
- [ ] No new `any`, no new raw SQL string concatenation, no new barrel file.
