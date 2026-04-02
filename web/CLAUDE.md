# Web Dashboard

React 19 + shadcn/ui + Radix UI + Tailwind CSS 4 + Framer Motion + Zustand

## Quick Commands

```bash
npm --prefix web install                   # install frontend deps
npm --prefix web run dev                   # dev server (http://localhost:5173)
npm --prefix web run build                 # production build
npm --prefix web run lint                  # ESLint (zero warnings enforced)
npm --prefix web run type-check            # TypeScript type checking
npm --prefix web run test                  # Vitest unit tests (coverage scoped to files changed vs origin/main)
npm --prefix web run analyze               # bundle size treemap (opens stats.html)
npm --prefix web run e2e                   # Playwright visual regression tests
npm --prefix web run e2e:update            # update Playwright screenshot baselines
npm --prefix web run lighthouse            # Lighthouse performance audit (target: 90+)
npm --prefix web run storybook             # Storybook dev server (http://localhost:6006)
npm --prefix web run storybook:build       # Storybook production build
```

## Package Structure

```text
web/src/
  api/            # Axios client, endpoint modules (20 domains), shared types
  components/     # React components: ui/ (shadcn primitives + SynthOrg core components), layout/ (app shell, sidebar with external link support, status bar); feature dirs added as pages are built
  hooks/          # React hooks (auth, login lockout, WebSocket, polling, optimistic updates, command palette, flash effects, status transitions, page data composition, count animation, auto-scroll, roving tabindex, breakpoint detection, update tracking, animation presets, settings dirty state, settings keyboard shortcuts, communication edges, artifact/project data composition)
  lib/            # Utilities (cn() class merging, semantic color mappers), Framer Motion presets, CSP nonce reader
  mocks/          # MSW request handlers for Storybook API mocking (handlers/)
  pages/          # Lazy-loaded page components (one per route); page-scoped sub-components in pages/<page-name>/ subdirs (e.g. tasks/, org-edit/, settings/)
  router/         # React Router config, route constants (incl. DOCUMENTATION -- external, not SPA-routed), auth/setup guards
  stores/         # Zustand stores (auth, WebSocket, toast, analytics, setup wizard, company, agents, budget, tasks, settings, sinks, providers, artifacts, projects, theme, and per-domain stores for each page)
  styles/         # Design tokens (--so-* CSS custom properties, single source of truth) and Tailwind theme bridge
  utils/          # Constants, error handling, formatting, logging
  __tests__/      # Vitest unit + property tests (mirrors src/ structure)
```

## Design System (MANDATORY)

### Component Reuse

**ALWAYS reuse existing components from `web/src/components/ui/`** before creating new ones. These are the shared building blocks -- every page composes from them:

| Component | Import | Use for |
|-----------|--------|---------|
| `StatusBadge` | `@/components/ui/status-badge` | Agent/task/system status indicators (colored dot + optional built-in label toggle) |
| `MetricCard` | `@/components/ui/metric-card` | Numeric KPIs with sparkline, change badge, progress bar |
| `Sparkline` | `@/components/ui/sparkline` | Inline SVG trend lines with `color?` and `animated?` props (used inside MetricCard or standalone) |
| `SectionCard` | `@/components/ui/section-card` | Titled card wrapper with icon and action slot |
| `AgentCard` | `@/components/ui/agent-card` | Agent display: avatar, name, role, status, current task |
| `DeptHealthBar` | `@/components/ui/dept-health-bar` | Department utilization: animated fill bar + `health?` (optional, shows N/A when null) + `agentCount` (required) |
| `ProgressGauge` | `@/components/ui/progress-gauge` | Circular or linear gauge for budget/utilization (`variant?` defaults to `'circular'`, `max?` defaults to 100) |
| `StatPill` | `@/components/ui/stat-pill` | Compact inline label + value pair |
| `Avatar` | `@/components/ui/avatar` | Circular initials avatar with optional `borderColor?` prop |
| `Button` | `@/components/ui/button` | Standard button (shadcn) |
| `Toast` / `ToastContainer` | `@/components/ui/toast` | Success/error/warning/info notifications with auto-dismiss queue (mount `ToastContainer` once in AppLayout) |
| `Skeleton` / `SkeletonCard` / `SkeletonMetric` / `SkeletonTable` / `SkeletonText` | `@/components/ui/skeleton` | Loading placeholders matching component shapes (shimmer animation, respects `prefers-reduced-motion`) |
| `EmptyState` | `@/components/ui/empty-state` | No-data / no-results placeholder with icon, title, description, optional action button |
| `ErrorBoundary` | `@/components/ui/error-boundary` | React error boundary with retry -- `level` prop: `page` / `section` / `component` |
| `ConfirmDialog` | `@/components/ui/confirm-dialog` | Confirmation modal (Radix AlertDialog) with `default` / `destructive` variants and `loading` state |
| `CommandPalette` | `@/components/ui/command-palette` | Global Cmd+K search (cmdk + React Router) -- mount once in AppLayout, register commands via `useCommandPalette` hook |
| `InlineEdit` | `@/components/ui/inline-edit` | Click-to-edit text with Enter/Escape, validation, optimistic save with rollback |
| `AnimatedPresence` | `@/components/ui/animated-presence` | Page transition wrapper (Framer Motion AnimatePresence keyed by route) |
| `StaggerGroup` / `StaggerItem` | `@/components/ui/stagger-group` | Card entrance stagger container with configurable delay |
| `Drawer` | `@/components/ui/drawer` | Slide-in panel (`side` prop: left or right, default right) with overlay, spring animation, focus trap, Escape-to-close, optional header (`title`), `ariaLabel` for accessible name (one of `title` or `ariaLabel` required), and `contentClassName` override |
| `InputField` | `@/components/ui/input-field` | Labeled text input with error/hint display, optional multiline textarea mode |
| `SelectField` | `@/components/ui/select-field` | Labeled select dropdown with error/hint and placeholder support |
| `SliderField` | `@/components/ui/slider-field` | Labeled range slider with custom value formatter and aria-live display |
| `ToggleField` | `@/components/ui/toggle-field` | Labeled toggle switch (role="switch") with optional description text |
| `TaskStatusIndicator` | `@/components/ui/task-status-indicator` | Task status dot with optional label and pulse animation (accepts `TaskStatus`) |
| `PriorityBadge` | `@/components/ui/task-status-indicator` | Task priority colored pill badge (critical/high/medium/low) |
| `ProviderHealthBadge` | `@/components/ui/provider-health-badge` | Provider health status indicator (up/degraded/down/unknown colored dot + optional label) |
| `TokenUsageBar` | `@/components/ui/token-usage-bar` | Segmented horizontal meter bar for token usage (multi-segment with auto-colors, `role="meter"`, animated transitions) |
| `CodeMirrorEditor` | `@/components/ui/code-mirror-editor` | CodeMirror 6 editor with JSON/YAML modes, design-token dark theme, line numbers, bracket matching, `readOnly` support |
| `SegmentedControl` | `@/components/ui/segmented-control` | Accessible radiogroup with keyboard navigation, size variants (`sm`/`md`), generic `<T extends string>` typing |
| `ThemeToggle` | `@/components/ui/theme-toggle` | Radix Popover with 5-axis theme controls (color, density, typography, animation, sidebar), rendered in StatusBar |
| `LiveRegion` | `@/components/ui/live-region` | Debounced ARIA live region wrapper (`polite`/`assertive`) for real-time WS updates without overwhelming screen readers |
| `MobileUnsupportedOverlay` | `@/components/ui/mobile-unsupported` | Full-screen overlay at `<768px` viewports directing users to desktop or CLI; self-manages visibility via `useBreakpoint` |
| `LazyCodeMirrorEditor` | `@/components/ui/lazy-code-mirror-editor` | Suspense-wrapped lazy-loaded `CodeMirrorEditor` (drop-in replacement, defers ~200KB+ CodeMirror bundle) |
| `TagInput` | `@/components/ui/tag-input` | Chip-style multi-value input with add/remove, keyboard support (Enter to add, Backspace to remove), paste splitting |
| `MetadataGrid` | `@/components/ui/metadata-grid` | Key-value metadata grid for detail pages with configurable columns (2/3/4), density-aware spacing |
| `ProjectStatusBadge` | `@/components/ui/project-status-badge` | Project status dot with optional label (planning/active/on_hold/completed/cancelled, semantic colors) |
| `ContentTypeBadge` | `@/components/ui/content-type-badge` | MIME content type pill badge with semantic colors (JSON, PDF, Image, Text, etc.) |

### Design Token Rules

- **Colors**: use Tailwind semantic classes (`text-foreground`, `bg-card`, `text-accent`, `text-success`, `bg-danger`, etc.) or CSS variables (`var(--so-accent)`). NEVER hardcode hex values in `.tsx`/`.ts` files.
- **Typography**: use `font-sans` or `font-mono` (maps to Geist tokens). NEVER set `fontFamily` directly.
- **Spacing**: use density-aware tokens (`p-card`, `gap-section-gap`, `gap-grid-gap`) or standard Tailwind spacing. NEVER hardcode pixel values for layout spacing.
- **Shadows/Borders**: use token variables (`var(--so-shadow-card-hover)`, `border-border`, `border-bright`).

### Creating New Components

When a new shared component is needed (not covered by the inventory above):
1. Place it in `web/src/components/ui/` with a descriptive kebab-case filename
2. Create a `.stories.tsx` file alongside it with all states (default, hover, loading, error, empty)
3. Export props as a TypeScript interface
4. Use design tokens exclusively -- no hardcoded colors, fonts, or spacing
5. Import `cn` from `@/lib/utils` for conditional class merging

### What NOT to Do

- **Do NOT** recreate status dots inline -- use `<StatusBadge>`
- **Do NOT** build card-with-header layouts from scratch -- use `<SectionCard>`
- **Do NOT** create metric displays with `text-metric font-bold` -- use `<MetricCard>`
- **Do NOT** render initials circles manually -- use `<Avatar>`
- **Do NOT** create complex (>8 line) JSX inside `.map()` -- extract to a shared component
- **Do NOT** use `rgba()` with hardcoded values -- use design token variables

### Enforcement

A PostToolUse hook (`scripts/check_web_design_system.py`) runs automatically on every Edit/Write to `web/src/` files. It catches:
- Hardcoded hex colors and rgba values
- Hardcoded font-family declarations
- Hardcoded Framer Motion transition durations (should use `@/lib/motion` presets)
- New components without Storybook stories
- Duplicate patterns that should use existing shared components
- Complex `.map()` blocks that should be extracted

Fix all violations before proceeding -- do not suppress or ignore hook output.

## Post-Training Reference (TypeScript 6 & Storybook 10)

These tools were released after Claude's training cutoff. Key facts for correct code generation:

### TypeScript 6.0 (https://aka.ms/ts6)

- **`baseUrl` deprecated** -- will stop working in TS 7. Remove it; `paths` entries are relative to the tsconfig directory
- **`esModuleInterop` always true** -- cannot be set to `false`; remove explicit `"esModuleInterop": true` to avoid deprecation warning
- **`types` defaults to `[]`** -- no longer auto-discovers `@types/*`; must explicitly list needed types (e.g. `"types": ["vitest/globals"]`)
- **`DOM.Iterable` merged into `DOM`** -- `"lib": ["ES2025", "DOM"]` is sufficient, no separate `DOM.Iterable`
- **`moduleResolution: "classic"` and `"node10"` removed** -- use `"bundler"` or `"nodenext"`
- **`strict` defaults to `true`** -- explicit `"strict": true` is redundant but harmless
- **`noUncheckedSideEffectImports` defaults to `true`** -- CSS side-effect imports need type declarations (Vite's `/// <reference types="vite/client" />` covers this)
- **Last JS-based TypeScript** -- TS 7.0 will be rewritten in Go. Migration tool: `npx @andrewbranch/ts5to6`

### Storybook 10 (https://storybook.js.org/docs/releases/migration-guide)

- **ESM-only** -- all CJS support removed
- **Packages removed** -- `@storybook/addon-essentials`, `@storybook/addon-interactions`, `@storybook/test`, `@storybook/blocks` no longer published. Essentials (backgrounds, controls, viewport, actions, toolbars, measure, outline) and interactions are built into core `storybook`
- **`@storybook/addon-docs` is separate** -- must be installed and added to addons if using `tags: ['autodocs']` or MDX
- **Import paths changed** -- use `storybook/test` (not `@storybook/test`), `storybook/actions` (not `@storybook/addon-actions`)
- **Type-safe config** -- use `defineMain` from `@storybook/react-vite/node` and `definePreview` from `@storybook/react-vite` (must still include explicit `framework` field)
- **Backgrounds API changed** -- use `parameters.backgrounds.options` (object keyed by name) + `initialGlobals.backgrounds.value` (replaces old `default` + `values` array)
- **a11y testing** -- use `parameters.a11y.test: 'error' | 'todo' | 'off'` (replaces old `.element` and `.manual`). Set globally in `preview.tsx` to enforce WCAG compliance on all stories
- **Minimum versions** -- Node 20.19+, Vite 5+, Vitest 3+, TypeScript 4.9+
