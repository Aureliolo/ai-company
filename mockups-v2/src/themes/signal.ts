import type { ThemeConfig } from "./types.ts"
import { densityMedium } from "./density.ts"
import {
  cardEntranceStatusDriven,
  pageTransitionFade,
} from "./animations.ts"

export const signal: ThemeConfig = {
  id: "signal",
  label: "Signal",
  slug: "d",
  description:
    "Emerald-green accent, medium density, status-driven animation, persistent sidebar with badges",

  colors: {
    bgBase: "#080c0a",
    bgSurface: "#0d1210",
    bgCard: "#131a17",
    bgCardHover: "#19211e",
    border: "#1e2a26",
    borderBright: "#2a3d36",
    accent: "#10b981",
    accentDim: "#059669",
    accentGlow: "rgba(16, 185, 129, 0.15)",
    success: "#10b981",
    warning: "#f59e0b",
    danger: "#ef4444",
    textPrimary: "#ecfdf5",
    textSecondary: "#94b8a8",
    textMuted: "#7fa393",
  },

  typography: {
    fontMono: "'Geist Mono', monospace",
    fontSans: "'Geist Sans', sans-serif",
    pairing: "geist",
  },

  density: densityMedium,

  animation: {
    profile: "status-driven",
    cardEntrance: cardEntranceStatusDriven,
    pageTransition: pageTransitionFade,
    statusPulse: true, // pulses only on state transitions via CSS class toggle
    hoverLift: null,
    shimmer: false,
    staggerChildren: 0,
    springConfig: null,
  },

  chrome: {
    sidebarMode: "persistent",
    sidebarWidth: 210,
    sidebarCollapsedWidth: 210,
    statusBarVisible: true,
  },
}
