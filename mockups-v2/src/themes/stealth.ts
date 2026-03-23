import type { ThemeConfig } from "./types.ts"
import { densitySparse } from "./density.ts"
import {
  cardEntranceInstant,
  pageTransitionInstant,
} from "./animations.ts"

export const stealth: ThemeConfig = {
  id: "stealth",
  label: "Stealth",
  slug: "c",
  description:
    "Neutral gray only, sparse Linear-like layout, instant transitions, hidden sidebar",

  colors: {
    bgBase: "#09090b",
    bgSurface: "#111113",
    bgCard: "#18181b",
    bgCardHover: "#1f1f23",
    border: "#27272a",
    borderBright: "#3f3f46",
    accent: "#a1a1aa",
    accentDim: "#71717a",
    accentGlow: "rgba(161, 161, 170, 0.1)",
    success: "#d4d4d8", // brighter gray -- differentiable without hue
    warning: "#a1a1aa", // medium gray
    danger: "#ef4444", // only color: red for errors
    textPrimary: "#fafafa",
    textSecondary: "#a1a1aa",
    textMuted: "#8a8a93",
  },

  typography: {
    fontMono: "'IBM Plex Mono', monospace",
    fontSans: "'IBM Plex Sans', sans-serif",
    pairing: "ibm-plex",
  },

  density: densitySparse,

  animation: {
    profile: "instant",
    cardEntrance: cardEntranceInstant,
    pageTransition: pageTransitionInstant,
    statusPulse: false,
    hoverLift: null,
    shimmer: false,
    staggerChildren: 0,
    springConfig: null,
  },

  chrome: {
    sidebarMode: "hidden",
    sidebarWidth: 240,
    sidebarCollapsedWidth: 0,
    statusBarVisible: false,
  },
}
