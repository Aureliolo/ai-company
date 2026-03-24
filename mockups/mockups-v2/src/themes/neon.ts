import type { ThemeConfig } from "./types.ts"
import { densityDense } from "./density.ts"
import {
  cardEntranceAggressive,
  createHoverLiftGlow,
  pageTransitionScale,
} from "./animations.ts"

const accentGlow = "rgba(139, 92, 246, 0.2)"

export const neon: ThemeConfig = {
  id: "neon",
  label: "Neon",
  slug: "e",
  description:
    "Violet-purple accent, dense layout, aggressive animation with entrance effects and shimmers, compact sidebar",

  colors: {
    bgBase: "#0a0810",
    bgSurface: "#100e18",
    bgCard: "#16131f",
    bgCardHover: "#1d1a28",
    border: "#231e32",
    borderBright: "#352e48",
    accent: "#8b5cf6",
    accentDim: "#7c3aed",
    accentGlow,
    success: "#10b981",
    warning: "#f59e0b",
    danger: "#ef4444",
    textPrimary: "#ede9fe",
    textSecondary: "#a5a0c8",
    textMuted: "#8882a8",
  },

  typography: {
    fontMono: "'JetBrains Mono Variable', monospace",
    fontSans: "'Inter Variable', sans-serif",
    pairing: "jetbrains-inter",
  },

  density: densityDense,

  animation: {
    profile: "aggressive",
    cardEntrance: cardEntranceAggressive,
    pageTransition: pageTransitionScale,
    statusPulse: true,
    hoverLift: createHoverLiftGlow(accentGlow),
    shimmer: true,
    staggerChildren: 0.05,
    springConfig: { stiffness: 400, damping: 20 },
  },

  chrome: {
    sidebarMode: "compact",
    sidebarWidth: 56,
    sidebarCollapsedWidth: 56,
    statusBarVisible: true,
  },
}
