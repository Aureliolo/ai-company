---
title: Brand Identity & UX Design System
description: Visual identity, theme architecture, color system, typography, density, animation, and UI guidelines for the SynthOrg dashboard.
---

# Brand Identity & UX Design System

## Design Direction

**Chosen direction**: Warm Ops -- a warm, approachable aesthetic with balanced density and spring-physics interactions, combined with semantic state-driven color encoding where every color communicates system status rather than serving as decoration.

**Why this direction**: Warmth makes an AI operations tool feel approachable without losing professionalism. Tying color exclusively to state (green = rising, amber = attention, red = critical) gives operators instant comprehension of system health. The brand accent is a warm soft blue -- deliberately neutral so that semantic state colors dominate the visual hierarchy. Orange/amber means "attention needed," not "this is SynthOrg."

**What was rejected and why**: A cool blue-cyan palette (data center aesthetic) was too generic -- indistinguishable from Grafana/Datadog screenshots. A neutral gray palette (no hue) lacked enough identity to be recognizable. A high-energy violet/purple palette was visually fatiguing for sustained 8-hour use. These directions scored well on individual criteria but failed the combination of identity distinctiveness + sustained usability.

**Design influences**: Linear (clean layout, balanced density), Vercel (status-first design), Dust.tt (warm approachability), Grafana (data density as a user preference).

## Color System

### Semantic Color Tokens

Colors are **state-driven**, not decorative. Every colored element answers: "what is the system telling me?"

| Token | Purpose | Example hex | When to use |
|-------|---------|-------------|-------------|
| `accent` | Brand, interactive elements, links, focus rings, active nav | `#38bdf8` (warm soft blue -- tunable) | Default state, clickable things, brand identity |
| `accent-dim` | Muted brand, secondary interactive, onboarding | Derived from accent | Hover states, secondary info, less prominent interactive |
| `success` | Rising, improving, healthy, completed | `#10b981` (emerald) | Metrics trending up, tasks completed, agents active |
| `warning` | Declining, degrading, attention needed | `#f59e0b` (amber) | Metrics trending down, budget nearing limit, stale tasks |
| `danger` | Critical, error, immediate action | `#ef4444` (red) | Agent errors, budget exceeded, failed tasks |
| `text-primary` | Main content text | `#e2e8f0` | Headings, values, primary content |
| `text-secondary` | Supporting text | `#94a3b8` | Labels, descriptions, secondary info |
| `text-muted` | Least prominent text | `#8b95a5` | Timestamps, metadata, disabled items |
| `bg-base` | Page background | `#0a0a12` | Deepest background layer |
| `bg-surface` | Sidebar, elevated surfaces | `#0f0f1a` | Sidebar, panels, raised areas |
| `bg-card` | Card backgrounds | `#13131f` | All card containers |
| `border` | Default borders | `#1e1e2e` | Card borders, dividers |
| `border-bright` | Interactive/hover borders | `#2a2a3e` | Focus rings, hover states |

### Dynamic Color Assignment

Metric cards, sparklines, and trend indicators use colors dynamically based on direction of change:

| Data state | Color token | Rationale |
|------------|-------------|-----------|
| Improving / rising | `success` | Green = things getting better |
| Stable / nominal | `accent` or `text-muted` | Neutral -- no action needed |
| Declining / degrading | `warning` | Amber = attention warranted |
| Critical / threshold | `danger` | Red = act now |

This ensures operators instantly understand system state from colors alone, without reading values. The same metric card shows green when tasks are completing faster and amber when they are slowing down.

### How to Add a New Color Theme

Each theme is a single configuration object (~50 lines). All colors are CSS custom properties consumed via `var(--theme-*)` tokens. To add a new theme:

1. Create a new theme config (e.g. `themes/midnight.ts`) with all color tokens
2. Register it in the theme index
3. Done -- all components automatically pick up the new palette

No component code changes required. The 5 exploration themes (Ice Station, Warm Ops, Stealth, Signal, Neon) demonstrate this pattern -- each theme is ~50 lines of color token definitions with zero component changes.

## Typography

### Chosen Pairing

| Role | Font | Usage |
|------|------|-------|
| Monospace | Geist Mono (via @fontsource, self-hosted) | Data values, code, metrics, timestamps, agent names |
| Sans-serif | Geist Sans (via @fontsource, self-hosted) | Labels, descriptions, UI text, headings |

**Rationale**: Geist was designed by Vercel specifically for developer dashboards. Excellent readability at small sizes, clean number rendering in mono, professional but not clinical in sans.

**Typography is a theme axis**: other pairings (JetBrains Mono + Inter, IBM Plex Mono + IBM Plex Sans) are available and can be selected independently of colors.

### Self-Hosted Fonts

All fonts are bundled via `@fontsource` packages. No external CDN (Google Fonts) dependencies. This ensures:
- No GDPR/privacy issues from third-party font loading
- Consistent rendering regardless of network
- Faster first contentful paint (no font fetch waterfall)

## Density

Density is an **independent user preference**, not tied to theme colors.

| Level | Padding | Section gap | Grid gap | Metric size | Body size | Use case |
|-------|---------|-------------|----------|-------------|-----------|----------|
| Dense | `p-3` (12px) | `gap-3` (12px) | `gap-3` (12px) | `text-2xl` | `text-xs` | Power users, large monitors, data-heavy workflows |
| Balanced (default) | `p-4` (16px) | `gap-4` (16px) | `gap-4` (16px) | `text-3xl` | `text-sm` | General use, comfortable reading distance |
| Medium | `p-[14px]` | `gap-4` (16px) | `gap-4` (16px) | `text-2xl` | `text-xs` | Slightly tighter than balanced |
| Sparse | `p-5` (20px) | `gap-6` (24px) | `gap-6` (24px) | `text-3xl` | `text-sm` | Presentation mode, low information density tasks |

### How to Add a New Density Level

Create a new `ThemeDensity` object with padding, gap, and font size values. Register it in the density index. Components read density from the theme context -- no component changes needed.

## Animation

Animation is an **independent user preference**, controlling motion intensity.

| Profile | Card entrance | Hover | Page transition | Status pulse | Use case |
|---------|---------------|-------|-----------------|--------------|----------|
| Minimal | 200ms fade | None | Fade only | Subtle | Reduced motion preference, distraction-free |
| Spring | Spring physics | Lift + shadow | Slide | Yes | Playful, responsive feel |
| Instant | No animation | None | None | No | Maximum performance, zero latency feel |
| Status-driven | Fade | None | Fade | Only on state change | Animation earns attention -- only moving things changed |
| Aggressive | Slide + fade + scale | Lift + glow | Scale | Yes + shimmer | High energy, demo/presentation mode |

**Recommended default**: Status-driven. Animation should communicate state change, not decoration. Static elements stay still; only things that changed move.

## Sidebar

Sidebar mode is an **independent user preference**.

| Mode | Behavior | Width | Best for |
|------|----------|-------|----------|
| Rail | Always visible, icon + label | 220px | Standard desktop use |
| Collapsible (default) | Expanded by default, can collapse to icon rail. Remembers user preference. | 220px / 56px | Most users -- full nav when needed, compact when focused |
| Hidden | Hamburger toggle, content gets full width | 240px (overlay) | Maximum content area, presentation |
| Persistent | Always expanded with notification badges | 220px | High-interactivity workflows, many nav items |
| Compact | Always visible, icons prominent, text secondary | 56px | Small screens, secondary monitors |

### Persistence

Sidebar collapse state is persisted in user preferences. If a user collapses the sidebar, it stays collapsed across sessions until they expand it again.

## Theme Architecture

### Independent Axes

The theme system has 5 orthogonal axes that users can configure independently:

```text
Color Palette  x  Density  x  Typography  x  Animation  x  Sidebar Mode
```

This gives users full control without combinatorial explosion in theme definitions. A user can run "warm blue colors + dense layout + IBM Plex fonts + minimal animation + compact sidebar" without any custom theme code.

### Implementation Pattern

```text
ThemeProvider (React context)
  |-- sets CSS custom properties on wrapper div (--theme-accent, --theme-bg-base, etc.)
  |-- Tailwind @theme block maps --theme-* to Tailwind utility classes
  |-- Components use Tailwind classes (text-accent, bg-bg-card, border-border)
  |-- Density/animation read from theme context object
  |-- Sidebar mode selects which sidebar component to render
```

### Critical Implementation Note: Tailwind v4 CSS Layers

When using Tailwind v4 with `@import "tailwindcss"`, **all custom CSS resets MUST be inside `@layer base`**. Tailwind v4 uses CSS cascade layers, and unlayered styles (like `* { margin: 0; padding: 0; }`) have higher priority than layered utilities, silently overriding all spacing, padding, margin, and gap utilities.

```css
/* WRONG -- breaks all Tailwind spacing utilities */
* { margin: 0; padding: 0; }

/* CORRECT -- respects Tailwind cascade layers */
@layer base {
  * { margin: 0; padding: 0; }
}
```

This was discovered during the design exploration (#765) and caused layout breakage that was difficult to diagnose because the utilities appeared in the generated CSS but had no visual effect.

## Dark Mode

**Dark mode only** (confirmed in #762 research). No light mode planned. All color tokens assume dark backgrounds. WCAG AA contrast ratios are validated against dark card/surface backgrounds.

## Accessibility

- WCAG AA contrast minimum on all text (4.5:1 on backgrounds, 3:1 for large text)
- `prefers-reduced-motion` support planned (disable infinite animations, reduce transition durations)
- Keyboard navigation for all interactive elements
- `aria-hidden="true"` on decorative icons
- Escape key closes overlays/drawers

## Reference Materials

| Resource | Location |
|----------|----------|
| Design exploration mockups (5 variations) | `feat/765-design-exploration` branch, `mockups-v2/` (exploration artifacts, not production code) |
| Original winning prototype (C+D direction) | `research/762-ux-mockups` branch, `mockups/direction-cd/` |
| UX research document | `research/762-ux-mockups` branch, `docs/design/ux-research.md` |
| Parent issue (full UX overhaul) | #762 |
| Design exploration issue | #765 |
| Design tokens implementation | #775 |
| UX guidelines document | #767 |
