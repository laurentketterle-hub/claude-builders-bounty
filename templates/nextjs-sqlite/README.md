# Template: CLAUDE.md for a Next.js 15 + SQLite SaaS

An opinionated, production-ready `CLAUDE.md` for a greenfield SaaS project built with
**Next.js 15 (App Router)**, **React 19**, **TypeScript**, and **SQLite**
(`better-sqlite3` or Turso), with **Drizzle ORM**, **Zod**, **Auth.js/Lucia**, and
**Tailwind CSS v4**.

## Usage

1. Scaffold the app:

   ```bash
   pnpm create next-app@latest my-saas --ts --app --tailwind --eslint
   cd my-saas
   ```

2. Copy `CLAUDE.md` to the project root.

3. Add the stack it assumes (`drizzle-orm`, `better-sqlite3`, `zod`, `auth.js`), then
   point Claude Code at the project — it will pick up these conventions without
   further prompting.

## Why this is opinionated (not generic)

Every rule states *why* it exists. A few positions this file deliberately takes:

- **App Router + Server Components only** — the Pages Router and client-side data
  fetching are excluded by name.
- **Drizzle over Prisma/TypeORM** — SQL-first, near-zero overhead, reviewable
  migrations, which fits SQLite's "one file, zero ops" philosophy.
- **Server Actions for *all* internal mutations**, with `app/api/` reserved strictly
  for external webhooks.
- **Integer cents for money, forward-only migrations, Zod at every boundary** — the
  three choices that prevent the most production incidents in a small SaaS.
