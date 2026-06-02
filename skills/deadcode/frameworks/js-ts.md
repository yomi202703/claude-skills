# JS/TS

## LENSES

All lenses output schema: `[{file, line, name, kind, lens, safety}]`. Monorepo (`pnpm-workspace.yaml` / `turbo.json` / `nx.json` / `lerna.json`): knip handles workspaces in one run.

### L1 — knip strict production (safety: 2)

Requires `entry` patterns in `knip.json` to carry `!` suffix for production marking. If `knip.json` is absent, create a minimal one auto-detecting `main` from `package.json`.

```
npx -y knip --production --strict --reporter json \
  | jq '[
      (.files // [] | map({file: ., line: 1, name: null, kind: "file", lens: "knip-orphan", safety: 1})),
      (.issues // [] | map(.exports // {} | to_entries | map(.value | map({file, line, name: .symbol, kind: "export", lens: "knip", safety: 2}))) | flatten),
      (.issues // [] | map(.dependencies // [] | map({file: "package.json", line: 0, name: ., kind: "dep", lens: "knip-dep", safety: 1}))) | flatten
    ] | flatten'
```

knip 単体で L1 (unused export), L2 (orphan file), unused dep を兼ねる。`--fix` で auto-removable (unused import / unused devDep) は即適用可能だが、本 skill では Phase 3a で per-commit に管理するため使わない。

### L3 — unreachable code (safety: 1)

`tsc --noEmit --noFallthroughCasesInSwitch --allowUnreachableCode false` を実行し diagnostic を集める。

```
npx -y tsc --noEmit --noFallthroughCasesInSwitch --allowUnreachableCode false 2>&1 \
  | rg 'error TS7027|error TS\d+: Unreachable' \
  | awk -F'[(:)]' '{printf "{\"file\":\"%s\",\"line\":%s,\"name\":\"unreachable\",\"kind\":\"branch\",\"lens\":\"unreachable\",\"safety\":1}\n", $1, $2}' \
  | jq -s '.'
```

## TEST_CMD

Run `scripts.test` from `package.json`: `npm test` / `pnpm test` / `yarn test` (pick by lockfile).
Typecheck: `scripts.typecheck` if defined, else `npx tsc --noEmit`.

## FRAMEWORK_HOOKS (skip — treated as live)

### File-name / decorator conventions

- Next.js app router: `app/**/page.tsx` `app/**/layout.tsx` `app/**/route.ts` `app/**/loading.tsx` `app/**/error.tsx` `app/**/not-found.tsx` `app/**/template.tsx` `middleware.ts` `instrumentation.ts`
- Next.js pages: `pages/**/*.{tsx,jsx,ts,js}` all default exports, `pages/api/**` all default exports, `getServerSideProps` / `getStaticProps` / `getStaticPaths`
- Remix: `app/routes/**` all exports, `loader` / `action` / `default` / `meta` / `links` / `headers` / `ErrorBoundary` / `CatchBoundary`
- Astro: `src/pages/**`, `getStaticPaths`
- Vite: anything reachable from `src/main.tsx` / `index.html`
- Storybook: `*.stories.{ts,tsx,js,jsx,mdx}` all exports
- Vitest/Jest: `*.test.{ts,tsx,js,jsx}` `*.spec.*` all exports

### React

- Default-exported component functions (treated as routes in Next.js / Remix / Astro)
- `displayName`
- Lifecycle hooks like `getInitialProps` / `getDerivedStateFromProps`

### NestJS / DI

- `@Injectable()` / `@Module()` / `@Controller()` classes
- `@Get()` / `@Post()` / `@Put()` / `@Delete()` / `@Patch()` handlers
- `@WebSocketGateway()` / `@SubscribeMessage()`

### Express / runtime-routed handlers

- functions registered via `app.get(...)` / `app.post(...)` / `app.put(...)` / `app.delete(...)` / `app.use(...)` / `router.<verb>(...)` — invoked by the framework, never referenced directly

### CommonJS barrel / re-export chains

- `module.exports = require('./x')` and `exports.Y = require('./y').Y` re-exports — knip's resolver can miss these chains, so a symbol reachable only through a CJS barrel reads as unused. Treat the re-exported target as live; verify with `rg` for the `require('./<file>')` link before trusting an "unused" verdict.

### Monorepo

- Cross-package imports (`packages/a/src` → `packages/b/src`) are only resolved when knip runs with the workspace config. A single root-`package.json` run misses them and floods false positives. Ensure `knip.json` declares the workspaces (or run knip workspace-aware); do not delete a cross-package export found by a root-only scan.

### TypeScript types

- `interface` / `type` field declarations
- `declare module` contents
- `enum` members (may exist for external API stability)

### File-name conventions

- `index.ts` / `index.tsx` re-exports — always keep
- `*.d.ts` declarations
- `__tests__/` directories

## ENTRYPOINTS

Knip auto-detects `main` / `bin` / `exports` from `package.json`. Build orchestrators and non-standard entry files (`taskfile.js`, `gulpfile.js`, `scripts/*.{ts,js}`, `bin/*`) are not auto-detected and must be registered as entries, or everything they reach reads as orphaned. Custom script entries: add to `knip.json`:

```json
{
  "entry": ["src/index.ts", "scripts/*.ts", "bin/cli.ts", "taskfile.js"],
  "project": ["src/**/*.ts", "scripts/**/*.ts"]
}
```
