# CLAUDE.md — Next.js + SQLite SaaS Template

## Project Stack
- **Framework:** Next.js 15 (App Router)
- **Database:** SQLite via better-sqlite3
- **Language:** TypeScript (strict mode)
- **Auth:** NextAuth.js v5
- **Styling:** Tailwind CSS 4
- **ORM:** Drizzle ORM

## Project Structure
```
src/
  app/           # Next.js App Router pages & API routes
    (auth)/      # Auth-protected routes
    api/         # API route handlers
  components/    # Shared React components
    ui/          # Base UI primitives (Button, Input, Card, etc.)
  lib/           # Business logic, utilities
    db/          # Database schema, migrations, queries
    auth/        # Auth configuration & helpers
  types/         # Shared TypeScript types
drizzle/         # Drizzle migrations (auto-generated)
```

## Naming Conventions
- **Files:** kebab-case (`user-profile.tsx`, `auth-helpers.ts`)
- **Components:** PascalCase (`UserProfile`, `SubmitButton`)
- **Functions:** camelCase (`getUserById`, `validateEmail`)
- **Database tables:** snake_case plural (`user_profiles`, `api_keys`)
- **Environment variables:** UPPER_SNAKE_CASE prefixed with `NEXT_PUBLIC_` for client

## Dev Commands
```bash
npm run dev          # Start dev server on :3000
npm run build        # Production build
npm run lint         # ESLint check
npm run format       # Prettier format
npm run db:generate  # Generate Drizzle migrations
npm run db:migrate   # Apply migrations
npm run db:studio    # Open Drizzle Studio on :4983
npm run test         # Vitest test suite
npm run test:e2e     # Playwright E2E tests
```

## Patterns to Follow
1. **Server Components first** — use `'use client'` only when absolutely necessary (state, effects, browser APIs)
2. **Data fetching in Server Components** — use `cache()` for deduplication, never fetch in client components
3. **API routes return typed responses** — always define `type ApiResponse<T> = { data?: T; error?: string }`
4. **Mutations via Server Actions** — prefer over API routes for form submissions
5. **Database queries in `lib/db/queries/`** — never inline SQL in components
6. **Zod validation on all inputs** — API routes, Server Actions, even internal function params in critical paths
7. **Error boundaries at route level** — `error.tsx` per route segment, not global
8. **Loading states with Suspense** — one `<Suspense>` per async component, skeleton placeholders

## Anti-Patterns to Avoid
- **NEVER** use `any` — always define proper types
- **NEVER** import server code (`fs`, `path`) in client components
- **NEVER** pass entire database rows to client components — strip sensitive fields
- **NEVER** use `fetch` with hardcoded URLs — use relative paths or env vars
- **NEVER** skip error handling in Server Actions — always `try/catch` and return typed errors
- **NEVER** mix Drizzle query builders with raw SQL in the same file — pick one style per query module

## Database Migration Rules
1. Always create a new migration file — never modify existing ones
2. Test migrations both up AND down before committing
3. Include data migrations (not just schema) when adding required columns
4. Run `db:studio` after migrate to visually verify

## Testing Philosophy
- Unit tests for `lib/` utilities (Vitest)
- Integration tests for database queries with in-memory SQLite
- E2E tests for critical user flows (signup → create → view)
- Never test implementation details — test behavior

## Environment Variables
```
DATABASE_URL=file:./data.db
AUTH_SECRET=generate-with-openssl
AUTH_GOOGLE_ID=...
AUTH_GOOGLE_SECRET=...
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

## Deployment Guide
**Target:** Vercel (primary) or Docker on any VPS.

### Vercel (Recommended)
```bash
npm run build          # Verify production build locally
npx vercel --prod      # Deploy to production
```
- Set all env vars in Vercel dashboard (NOT `.env.local`)
- SQLite: use `libsql` (Turso) for distributed reads or stick to serverless-friendly `better-sqlite3` on Vercel Functions
- Enable Analytics + Speed Insights in Vercel dashboard

### Docker
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/drizzle ./drizzle
EXPOSE 3000
CMD ["node", "server.js"]
```
- Mount `data.db` as a Docker volume for persistence
- Run `npm run db:migrate` in an init container before starting

## Performance Patterns
1. **Route Segment Config** — export `revalidate` or `dynamic` per page, not globally
2. **Image Optimization** — always use `next/image` with explicit `width`/`height`
3. **Bundle Analysis** — run `ANALYZE=true npm run build` before every PR
4. **Database Indexes** — add indexes on every column used in `WHERE`, `JOIN`, or `ORDER BY`
5. **Streaming** — use `loading.tsx` + React Suspense for above-the-fold content
6. **Font Loading** — use `next/font/google` with `display: 'swap'`

## Common Pitfalls & Debugging
| Symptom | Likely Cause | Fix |
|---|---|---|
| `SQLITE_BUSY` | Concurrent writes | Use WAL mode: `PRAGMA journal_mode=WAL` |
| `NEXT_REDIRECT` in try/catch | Redirect thrown as error | Let it propagate, don't catch |
| Hydration mismatch | `Date.now()`, `Math.random()` in render | Move to `useEffect` or `suppressHydrationWarning` |
| `Module not found: fs` | Server import in client component | Add `'use server'` directive or move to `lib/` |
| Stale data after mutation | Missing `revalidatePath()` | Call `revalidatePath()` in Server Action |

## Security Checklist
- [ ] All user inputs validated with Zod schemas
- [ ] CSRF protection via NextAuth built-in (POST-only Server Actions)
- [ ] API rate limiting via `@upstash/ratelimit` on auth and payment routes
- [ ] CSP headers via `next.config.js` `headers()` function
- [ ] Environment variables NEVER prefixed with `NEXT_PUBLIC_` unless explicitly needed client-side
- [ ] Database queries always use parameterized statements (Drizzle handles this)
- [ ] No secrets in git history — use `.gitignore` + `env.template` pattern

## API Design Conventions
- **GET** `/api/[resource]` — list (paginated, `?page=&limit=`)
- **GET** `/api/[resource]/[id]` — single item (404 if not found)
- **POST** `/api/[resource]` — create (return 201 + created resource)
- **PATCH** `/api/[resource]/[id]` — partial update (return 200)
- **DELETE** `/api/[resource]/[id]` — soft-delete preferred (set `deleted_at`)
- Always return `{ data, error }` shape, never raw values
- Use HTTP status codes properly (200, 201, 400, 401, 403, 404, 409, 500)

## Git Workflow
- Branch naming: `feat/`, `fix/`, `chore/`, `docs/` prefixes
- Commit messages: conventional commits (`feat:`, `fix:`, `chore:`)
- PRs require: passing CI, 1 review, linear history (rebase, no merge commits)
- Never commit `.env` files — use `.env.example` with dummy values

## Accessibility (a11y) Checklist
- [ ] All interactive elements are keyboard-navigable (Tab, Enter, Escape)
- [ ] Form inputs have associated `<label>` elements with `htmlFor`
- [ ] Color contrast ratio ≥ 4.5:1 for text, ≥ 3:1 for large text
- [ ] Images have descriptive `alt` text (empty `alt=""` for decorative images)
- [ ] Page has a single `<h1>` and logical heading hierarchy (h1→h2→h3)
- [ ] `aria-label` on icon-only buttons and links
- [ ] Focus indicators visible (`focus-visible:ring-2` in Tailwind)
- [ ] Use `@next/mdx` or `react-aria` for complex interactive components

## Observability & Monitoring
- **Logging:** Use `pino` for structured JSON logging in production; `console.log` only in dev
- **Error Tracking:** Integrate Sentry (`@sentry/nextjs`) for production error monitoring
- **Performance:** Enable Vercel Analytics + Web Vitals reporting
- **Health Check:** Expose `GET /api/health` returning `{ status: "ok", db: "connected" }`
- **Database Monitoring:** Log slow queries (>100ms) in development with Drizzle's `logger: true`

## Dependency Management
1. **Pin exact versions** in `package.json` — no `^` or `~` ranges
2. **Audit weekly** — `npm audit` and address HIGH/CRITICAL immediately
3. **Minimal dependencies** — prefer `fetch()` over `axios`, native `crypto` over `bcryptjs` when possible
4. **Lockfile committed** — `package-lock.json` always tracked in git
5. **Bundle impact** — run `npx next-bundle-analyzer` before adding new packages >50KB

## Quick Start for New Developers
```bash
git clone <repo-url>
cp .env.example .env.local     # Fill in real values
npm ci                          # Exact install from lockfile
npm run db:generate             # Create initial migration
npm run db:migrate              # Apply migration
npm run dev                     # Start at http://localhost:3000
```
Open `http://localhost:3000/api/health` — should return `{"status":"ok"}`.

## Multi-Tenancy Patterns (B2B SaaS)
When building a multi-tenant SaaS:
1. **Row-Level Security** — every table gets `tenant_id` column; queries always filter by `tenant_id`
2. **Tenant Resolution** — extract tenant from subdomain (`tenant.app.com`) or JWT claim, never from request body
3. **Isolation** — one SQLite database file per tenant OR shared DB with strict `WHERE tenant_id = ?` on every query
4. **Migrations** — always include `tenant_id` in new tables from day 1; retrofitting is painful
5. **Billing** — integrate Stripe via `@stripe/stripe-js` for client-side, `stripe` npm package for server-side webhooks

