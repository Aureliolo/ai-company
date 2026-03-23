---
title: UX Research & Design Direction
description: Research findings, design direction decisions, and framework choices for the dashboard UX overhaul (#762).
---

# UX Research & Design Direction

> Research conducted March 2026 for [#762](https://github.com/Aureliolo/synthorg/issues/762).
> This document captures the findings, decisions, and rationale so future work can reference them.

---

## Executive Summary

The SynthOrg web dashboard requires a complete UX overhaul. The current implementation (Vue 3 + PrimeVue + Tailwind) is functional but suffers from generic design, static data presentation, poor usability, and no visual identity. Research across 8 AI agent platforms, 7 best-in-class dashboards, 4 design directions, and multiple framework/component library combinations led to the following decisions:

- **Design direction**: Mission Control + Ambient (C+D) — dense data panels with calm typography
- **Framework**: OPEN — Vue 3 + shadcn-vue or React + shadcn/ui (requires in-depth study, see Framework section)
- **Theme**: Dark mode primary
- **Target**: v0.5.0
- **Scope**: Total rewrite of all dashboard pages (setup wizard is the only thing worth preserving conceptually)

---

## Current State Assessment

### What works
- Setup wizard: clear progress indicators, step validation, back-navigation, completion summary
- WebSocket infrastructure: wired on 6/15 pages, store handlers for real-time updates
- ECharts integration, PrimeVue DataTables, Edit mode toggle pattern (GUI/JSON/YAML)
- Error boundaries, empty states, loading skeletons (page-level)

### What's broken (everything else)
- **Generic "vibe-coded" feel**: every page looks like a default PrimeVue template
- **Static data everywhere**: cards and tables just display data with no trends, context, or visual feedback
- **No visual identity**: no brand, no personality, no distinction from any other dashboard
- **Poor information architecture**: wrong things are prominent, important stuff is buried
- **No real-time indicators**: WebSocket exists but UI updates are silent
- **Unused infrastructure**: `useOptimisticUpdate` (zero consumers), `usePolling` (zero consumers)
- **Duplicated code**: save/dirty/reset pattern copy-pasted across Settings, Providers, Company
- **Inconsistent components**: AgentCard looks different on every page it appears

### Pages by interactivity level
- **High**: TaskBoard, SetupPage, SettingsPage, ProvidersPage, CompanyPage
- **Medium**: Dashboard, ApprovalQueue, MeetingLogs, MessageFeed
- **Low**: AgentProfiles, OrgChart, BudgetPanel, AgentDetail
- **None**: ArtifactBrowser (stub)

---

## Competitor Analysis

### AI Agent Platforms (8 analyzed)

| Platform | Stack | Visual Identity | Agents Feel Alive | Best Idea | Worst Pattern |
|----------|-------|----------------|-------------------|-----------|---------------|
| CrewAI | React/Next.js | Marketing: yes. Product: generic | No | Manager agent delegation hierarchy | CI/CD-style log streams |
| AutoGen Studio | FastAPI + Gatsby + Tailwind | None | No | Agent/team gallery for browsing | Group chat as only interaction |
| Dify | Python + React | Yes (blue/purple, design-tool) | Partially (canvas nodes light up) | Node-by-node execution highlighting | "Every agent is an app" |
| LangFlow | Python + TypeScript | Weak (generic flow builder) | No | Structured tool-call visualization | Node-graph-as-organization |
| AgentOps | Next.js + Tailwind | Moderate (purple, monitoring) | No (stateless sessions) | Session Waterfall timeline | Anonymous session model |
| Dust | TypeScript + Next.js + Geist | Strongest (green, warm) | Partially | Frames: agent output as interactive components | Everything funnels into chat |
| Relevance AI | Nuxt.js (Vue 3) | Good (avatars, workforce language) | Best (pulsing status) | Avatar cards with role + autonomy + tool badges | Canvas-as-workflow |
| Letta | Python + Next.js | Moderate (memory palace) | Conceptually | Live memory mutation visualization | Single-agent IDE metaphor |

### What NO competitor does (SynthOrg must invent)

1. **Living org chart** — organization as a spatial artifact reflecting real-time state
2. **Agent biography / work history** — career arc, reputation, performance narrative
3. **Meeting rooms** — synchronous organizational rituals (standups, reviews, decisions)
4. **Budget as organizational P&L** — not a billing tab, but a management dashboard
5. **Organizational health / mood** — "is the company performing well?" as a visual layer

### Best-in-Class Dashboards (7 analyzed)

| Product | Signature Strength | Tech Stack |
|---------|-------------------|------------|
| Vercel | Deployment state "arrives", doesn't flash. Geist font. | React + Next.js, Geist design system, Tailwind |
| Linear | Keyboard-first (Cmd+K everything). LCH color space. Navigation recedes, content luminous. | React, custom CSS, LCH themes |
| Railway | Service topology as spatial canvas — infrastructure has a shape | React (assumed) |
| Supabase | SQL editor as first-class peer to GUI. Respects the developer. | React + Next.js, Radix + shadcn/ui + Tailwind |
| Grafana | Explore dual-split queries, 30fps live streaming | React, Saga design system (OSS) |
| Datadog | Metrics → traces → logs pivot. Trace flame graphs. | React, DRUIDS (150+ components) |
| Sentry | Stacktrace progressive disclosure. Relevant frames elevated. | React, Emotion CSS-in-JS, OSS |

### Key patterns to adopt
- Linear's "navigation chrome recedes, content stays luminous"
- Linear's LCH color space for accessible custom theming
- Vercel's "status arrives rather than flashing" (meaningful animation)
- AgentOps' Session Waterfall as a live org-level event feed
- Dify's canvas execution highlighting applied to org chart
- Relevance AI's agent avatar cards with role + autonomy level

---

## Design Directions Explored

### Four directions prototyped

| Direction | Description | Prototype |
|-----------|-------------|-----------|
| **C+D: Mission Control + Ambient** | Dense data panels, sparklines, department health bars, activity stream, budget forecast. Professional command center with calm typography. | React + Tailwind |
| **B+D: Neural Network + Ambient** | Force-directed graph centerpiece, glowing agent nodes, pulsing communication edges, ambient activity tray. | Vue 3 + Tailwind + D3 |
| **D+B: Ambient Org + Graph Accent** | Typography-first, prose-driven status, mini org graph widget, calm and restrained. | React + Tailwind |

All prototypes served via Podman at `http://chs00013.eu.hcnet.biz:8080/` with 3 pages each (Dashboard, Org Chart, Agent Profile).

### Evaluation Results

**External reviewer feedback** (developer, management perspective):

| Dimension | C+D Mission Control | B+D Neural Network | D+B Ambient Org |
|-----------|--------------------|--------------------|-----------------|
| **Management utility** | Best — all facts consolidated, resource planning ready | Fancy but no utility | Just an activity stream |
| **Developer utility** | Has all nav points, comprehensive | Can't do anything with it | Maybe useful for agent availability |
| **Overview clarity** | Clear winner — "you can break everything down" | Org chart is redundant with overview | Too basic |
| **Looks like AI bullshit?** | No — "basic overview layout, nothing fancy" | Most — "funny shit but not business-usable" | No — "basic AF, won't win beauty prizes" |
| **Would work with** | Yes — "extremely valuable for planning" | No — "fun on a screen, not in business" | Partially — "for cost accounting" |

### Winner: C+D Mission Control + Ambient

Won on every practical dimension. Key strengths:
- Information density without overwhelm
- All organizational data accessible from one view
- Professional, operationally honest
- Highest AI producibility (tables, charts, status indicators = well-understood patterns)
- Natural home for numeric data (costs, latency, token counts, approval ages)

### Elements to incorporate from other directions

- **From D+B (Ambient)**: Typography hierarchy, prose-style status sentences, agent names as primary identifiers (not IDs), humanizing language ("People" not "Agents")
- **From B+D (Neural Network)**: Force-directed graph as a secondary visualization on the Org Chart page (not as the primary dashboard), agent status via glow/dim encoding
- **From D+B (Ambient)**: Agent profile as a narrative ("Currently working on..."), performance described in prose alongside metrics

---

## Framework & Component Library Decision

### Research findings

| Stack | AI Writability | Identity Freedom | Determinism | Ecosystem |
|-------|:-:|:-:|:-:|:-:|
| **React + shadcn/ui + Tailwind** | 5 | 5 | 5 | 5 |
| **Vue 3 + shadcn-vue + Tailwind** | 4 | 5 | 5 | 4 |
| Vue 3 + PrimeVue (styled) | 4 | **2** | 2 | 5 |
| Vue 3 + PrimeVue (unstyled) | 3.5 | 3.5 | 3.5 | 5 |
| Vue 3 + Ark UI + Tailwind | 4 | 5 | 5 | 3.5 |
| Svelte 5 + Bits UI | 3 | 5 | 5 | 3 |

### Decision: OPEN — requires in-depth study

The framework decision is deliberately left open. Both paths are viable. The choice should be made after building a deeper proof-of-concept that tests interactive components (not just visual mockups).

**Option A: Vue 3 + shadcn-vue + Reka UI + Tailwind**

Pros:
- No migration cost — existing stores, composables, router, test infrastructure preserved
- VueFlow (org chart) stays as-is; no API migration
- shadcn-vue mirrors shadcn/ui patterns; LLM training data partially transfers
- Vue's `.vue` SFC format gives AI clean single-file context
- PrimeVue is the problem, not Vue (identity freedom: PrimeVue 2/5, shadcn-vue 5/5)

Cons:
- AI writability 4/5 vs React's 5/5 (smaller training corpus)
- No v0.dev integration (React-only)
- Vercel AI SDK streaming components are React-first
- Slightly more Vue-specific LLM quirks (reactive declarations, `defineEmits` TS edge cases)

**Option B: React + shadcn/ui + Tailwind**

Pros:
- Maximum AI writability (5/5) — largest training corpus, v0.dev trained on this exact stack
- 78% of AI-first teams default to React (Groovyweb 2026 survey)
- 15-25% faster AI iteration cycles reported (but from teams starting fresh, not migrating)
- shadcn/ui is the most AI-trained component library in existence
- React Flow is mature equivalent to VueFlow

Cons:
- Total rewrite of: Pinia stores → Zustand/Jotai, Vue Router → React Router, composables → hooks, Vitest → Vitest (stays) but test utilities change, VueFlow → React Flow
- Build pipeline, CI, dev tooling all need reconfiguring
- The winning direction (Mission Control) won on design, not framework — equally buildable in Vue

**Key data points:**
- DesignBench (2025): React and Vue are statistically tied on compilation success rates (0.95-0.97)
- The gap is ecosystem + tooling + training data volume, not code quality
- PrimeVue's "template look" problem is structural (even unstyled mode is "override what Prime ships")
- Both frameworks score 5/5 on identity freedom when paired with shadcn
- Both score 5/5 on determinism with Tailwind

**Next step needed:** Build the same interactive page (e.g., Dashboard with working filters, WebSocket simulation, Cmd+K palette) in BOTH frameworks and compare AI output quality, development speed, and code maintainability.

---

## Design System Principles

1. **Data is never just a number** — every metric shows trend, context, or comparison (sparklines, deltas, forecasts)
2. **Real-time means visible** — WebSocket updates produce visual feedback (flash, badge, state transition animation)
3. **One component, one look** — AgentCard, StatusBadge, MetricCard are identical everywhere they appear
4. **Navigation recedes, content shines** — sidebar and chrome are muted; the data is luminous (Linear's principle)
5. **Status arrives, doesn't flash** — state changes use meaningful 200ms transitions, not jarring swaps (Vercel's principle)
6. **Progressive disclosure** — summary first, detail on hover/click, full view on navigate
7. **Keyboard-first** — Cmd+K command palette, arrow keys in lists, Enter to open, Escape to close
8. **Typography carries information** — type weight, size, and opacity encode importance; minimize reliance on color alone
9. **Prose alongside metrics** — agent profiles, org health, and status are described in sentences, not just numbers
10. **Every pixel earns its place** — no decorative elements, no empty chrome; if it doesn't serve data, remove it

---

## Color System

Based on the Mission Control + Ambient prototype:

| Token | Value | Usage |
|-------|-------|-------|
| `bg-primary` | `#0a0a12` | Page background |
| `bg-surface` | `#0f0f1a` | Card/panel background |
| `bg-elevated` | `#13131f` | Hover states, active items |
| `accent` | `#22d3ee` (cyan) | Active/nominal states, interactive elements |
| `success` | `#10b981` (emerald) | Healthy, completed, nominal |
| `warning` | `#f59e0b` (amber) | Warnings, pending, degraded |
| `danger` | `#ef4444` (red) | Critical, failed, error |
| `text-primary` | `#f1f5f9` | Primary text |
| `text-secondary` | `#94a3b8` | Secondary text, labels |
| `text-muted` | `#475569` | Timestamps, tertiary info |
| `border` | `#1e1e2e` | Subtle borders |

**Typography:**
- Data values: JetBrains Mono (monospace)
- Labels and prose: Inter (sans-serif)
- Spacing: 8px grid

---

## Visual QA Workflow

Three complementary verification methods for the implementation phase:

1. **Storybook** — build components in isolation, visual regression via Chromatic
2. **Playwright screenshots** — automated baseline screenshots after each change, attached to conversation
3. **Dev server + manual review** — user opens dev server, sends feedback/screenshots

---

## SynthOrg Differentiators to Implement

These are UX patterns that no competitor has. They define SynthOrg's visual identity:

### 1. Living Org Chart
The org chart is not a static diagram — it reflects real-time organizational state. Agent nodes show status (active/idle/error via color), department groups show health (green/amber/red via fill), and communication flows are visible as edge activity. Click any node to drill into detail.

### 2. Agent Biography
Every agent has a profile that reads like a team member bio: hire date, role history, task completion stats, performance narrative in prose, recent work as content cards, communication connections. Not a config form — a character sheet.

### 3. Budget as Organizational P&L
Cost is visualized as a management dashboard: burn rate slope chart with forecast projection, department allocation breakdown (pie/donut), per-agent efficiency metrics, threshold alerts. The CFO agent's optimization decisions are surfaced as events in the activity stream.

### 4. Organizational Health Layer
At-a-glance org health overlaid on department views: horizontal progress bars (green fill = healthy throughput, amber = degraded, red = stagnated). Bottleneck detection. Stagnation alerts. Like a manager's gut feel, made visual.

---

## Existing v0.5 Issues (no duplication)

| Issue | Scope | Relationship |
|-------|-------|-------------|
| #674 | Interactive org chart with CRUD | #762 sub-issues add status/health visualization on top of #674's CRUD |
| #565 | Sink config UI in settings | Separate settings feature, not UX overhaul |
| #238 | Company builder wizard | Separate wizard feature |
| #247 | Visual workflow editor | Separate feature |
| #726 | Template comparison in setup | Setup wizard extension |
| #295 | Embed docs in dashboard | Separate feature |

---

## Reviewer Open Questions (to address in implementation)

From the external review, these product questions should inform the implementation:

1. **"Is this website meant to give the developer an overview of their company?"** — Yes, and also to manage it. The dashboard is the primary interface for monitoring and controlling the synthetic organization.
2. **"Can I create and execute workflows directly through the web interface?"** — Partially today (task creation, approval actions, meeting triggers). Full workflow creation is #247 (v0.5.9).
3. **"Who maintains all this info? Does it all come through an API?"** — All data comes from the REST/WebSocket API. The engine populates it automatically. Humans intervene via approvals and configuration.
4. **"Is this a template that a customer could customize (color, layout)?"** — Not currently. Theming (color customization) could be a future enhancement. Layout is fixed by design.
5. **"The neural network is nice-to-have, but why?"** — Validated concern. The force-directed graph is demoted to a secondary view on the Org Chart page, not the primary dashboard. It shows communication patterns and relationships, complementing the hierarchical org chart.

---

## Next Steps

1. Create focused GitHub sub-issues for implementation (workstream breakdown)
2. Set up shadcn-vue in the web/ directory, begin component library migration
3. Implement pages in priority order: Dashboard → Org Chart → Task Board → Budget → Agent Profiles → remaining pages
4. Set up Storybook + Playwright visual QA pipeline
5. Wire WebSocket to all pages (currently only 6/15)
