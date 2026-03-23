import type { ThemeConfig } from "./types.ts"
import { densityDense } from "./density.ts"
import {
  cardEntranceMinimal,
  pageTransitionFade,
} from "./animations.ts"

export const iceStation: ThemeConfig = {
  id: "ice-station",
  label: "Ice Station",
  slug: "a",
  description:
    "Cool cyan, dense Grafana-like layout, minimal animation, always-visible rail sidebar",

  colors: {
    bgBase: "#0a0a12",
    bgSurface: "#0f0f1a",
    bgCard: "#13131f",
    bgCardHover: "#181828",
    border: "#1e1e2e",
    borderBright: "#2a2a3e",
    accent: "#22d3ee",
    accentDim: "#0891b2",
    accentGlow: "rgba(34, 211, 238, 0.15)",
    success: "#10b981",
    warning: "#f59e0b",
    danger: "#ef4444",
    textPrimary: "#e2e8f0",
    textSecondary: "#94a3b8",
    textMuted: "#8b95a5",
  },

  typography: {
    fontMono: "'JetBrains Mono Variable', monospace",
    fontSans: "'Inter Variable', sans-serif",
    pairing: "jetbrains-inter",
  },

  density: densityDense,

  animation: {
    profile: "minimal",
    cardEntrance: cardEntranceMinimal,
    pageTransition: pageTransitionFade,
    statusPulse: false,
    hoverLift: null,
    shimmer: false,
    staggerChildren: 0,
    springConfig: null,
  },

  chrome: {
    sidebarMode: "rail",
    sidebarWidth: 200,
    sidebarCollapsedWidth: 200,
    statusBarVisible: true,
  },
}
