import type { ThemeConfig } from "./types.ts"
import { densityBalanced } from "./density.ts"
import {
  cardEntranceSpring,
  hoverLiftSubtle,
  pageTransitionSlide,
} from "./animations.ts"

export const warmOps: ThemeConfig = {
  id: "warm-ops",
  label: "Warm Ops",
  slug: "b",
  description:
    "Warm amber-gold accent, balanced density, spring physics, collapsible sidebar",

  colors: {
    bgBase: "#0c0a08",
    bgSurface: "#141210",
    bgCard: "#1a1816",
    bgCardHover: "#211f1c",
    border: "#2a2622",
    borderBright: "#3d3832",
    accent: "#f59e0b",
    accentDim: "#d97706",
    accentGlow: "rgba(245, 158, 11, 0.15)",
    success: "#10b981",
    warning: "#fb923c",
    danger: "#ef4444",
    textPrimary: "#f5f0eb",
    textSecondary: "#a8a093",
    textMuted: "#8a8279",
  },

  typography: {
    fontMono: "'Geist Mono', monospace",
    fontSans: "'Geist Sans', sans-serif",
    pairing: "geist",
  },

  density: densityBalanced,

  animation: {
    profile: "spring",
    cardEntrance: cardEntranceSpring,
    pageTransition: pageTransitionSlide,
    statusPulse: false,
    hoverLift: hoverLiftSubtle,
    shimmer: false,
    staggerChildren: 0.04,
    springConfig: { stiffness: 300, damping: 25 },
  },

  chrome: {
    sidebarMode: "collapsible",
    sidebarWidth: 220,
    sidebarCollapsedWidth: 56,
    statusBarVisible: true,
  },
}
