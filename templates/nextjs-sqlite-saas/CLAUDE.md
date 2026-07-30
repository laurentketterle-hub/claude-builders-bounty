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
