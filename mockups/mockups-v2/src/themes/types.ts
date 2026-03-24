import type { Variants, Transition, TargetAndTransition } from "framer-motion"

export type VariationSlug = "a" | "b" | "c" | "d" | "e"
export type VariationId =
  | "ice-station"
  | "warm-ops"
  | "stealth"
  | "signal"
  | "neon"
export type DensityLevel = "dense" | "balanced" | "sparse" | "medium"
export type AnimationProfile =
  | "minimal"
  | "spring"
  | "instant"
  | "status-driven"
  | "aggressive"
export type SidebarMode =
  | "rail"
  | "collapsible"
  | "hidden"
  | "persistent"
  | "compact"
export type TypographyPairing = "jetbrains-inter" | "geist" | "ibm-plex"

export interface ThemeColors {
  bgBase: string
  bgSurface: string
  bgCard: string
  bgCardHover: string
  border: string
  borderBright: string
  accent: string
  accentDim: string
  accentGlow: string // rgba version for shadows/glows
  success: string
  warning: string
  danger: string
  textPrimary: string
  textSecondary: string
  textMuted: string // must pass WCAG AA 4.5:1 on bgCard
}

export interface ThemeTypography {
  fontMono: string
  fontSans: string
  pairing: TypographyPairing
}

export interface ThemeDensity {
  level: DensityLevel
  cardPadding: string // tailwind class e.g. "p-3"
  sectionGap: string // tailwind class e.g. "gap-3"
  gridGap: string // tailwind class e.g. "gap-3"
  fontSize: {
    metric: string // e.g. "text-2xl"
    label: string // e.g. "text-[10px]"
    body: string // e.g. "text-xs"
    small: string // e.g. "text-[10px]"
  }
}

export interface ThemeAnimation {
  profile: AnimationProfile
  cardEntrance: Variants
  pageTransition: {
    initial: object
    animate: object
    exit: object
    transition?: Transition
  }
  statusPulse: boolean // whether status dots continuously pulse
  hoverLift: TargetAndTransition | null // hover animation for cards
  shimmer: boolean // loading shimmer effect
  staggerChildren: number // delay between staggered children (0 = no stagger)
  springConfig: { stiffness: number; damping: number } | null
}

export interface ThemeChrome {
  sidebarMode: SidebarMode
  sidebarWidth: number // px when expanded
  sidebarCollapsedWidth: number // px when collapsed (0 for hidden)
  statusBarVisible: boolean
}

export interface ThemeConfig {
  id: VariationId
  label: string
  slug: VariationSlug
  description: string
  colors: ThemeColors
  typography: ThemeTypography
  density: ThemeDensity
  animation: ThemeAnimation
  chrome: ThemeChrome
}
