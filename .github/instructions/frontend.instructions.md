---
applyTo: frontend/src/**/*.{ts,tsx}
---

# Frontend Instructions

## Structure
- Reusable components go in `frontend/src/components/`
- Page-level components go in `frontend/src/pages/`
- Custom hooks go in `frontend/src/hooks/`
- API client functions go in `frontend/src/services/api.ts`

## API Communication
- Use the existing fetch-based functions in `frontend/src/services/api.ts` — do not use `fetch` directly in components
- Authentication tokens are stored in `localStorage` as `access_token` and `refresh_token`
- Use the existing `useAuth` hook from `frontend/src/hooks/useAuth.ts` for auth state
- API base URL is configured via `VITE_API_URL` environment variable

## TypeScript
- TypeScript strict mode is enabled — all props and state must be typed; avoid `any`
- Define interfaces for all API response shapes
- The `vite-env.d.ts` file provides `import.meta.env` types — do not remove it
- `tsconfig.node.json` covers `vite.config.ts` — both are required

## UI Patterns
- Use `react-hot-toast` for user-facing notifications (already a dependency)
- Use React Router v6 `<Navigate>` for redirects in protected routes
- Use `useAuth()` hook to check authentication state in protected components
- Functional components with React Hooks only — no class components

## Build & Lint
- The project uses Vite (not Next.js) — `next.config.ts` is a leftover file and can be ignored
- Run `npm run build` to validate TypeScript (`tsc`) and build assets
- Run `npm run lint` to check ESLint rules
- Required dev dependencies: `tailwindcss@3`, `autoprefixer`, `terser` (all in package.json)
- Vitest is configured for testing: run `npm test`

## Adding New Pages
1. Create `frontend/src/pages/MyPage.tsx`
2. Import and add a route in `frontend/src/App.tsx`
3. Wrap with `<ProtectedRoute>` if authentication is required
4. Add navigation link in `frontend/src/components/Navbar.tsx` if needed
