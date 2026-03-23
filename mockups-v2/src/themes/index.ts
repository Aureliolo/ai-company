export type {
  VariationSlug,
  VariationId,
  DensityLevel,
  AnimationProfile,
  SidebarMode,
  TypographyPairing,
  ThemeColors,
  ThemeTypography,
  ThemeDensity,
  ThemeAnimation,
  ThemeChrome,
  ThemeConfig,
} from "./types.ts"

export {
  densityDense,
  densityBalanced,
  densitySparse,
  densityMedium,
} from "./density.ts"

export {
  cardEntranceMinimal,
  cardEntranceSpring,
  cardEntranceInstant,
  cardEntranceStatusDriven,
  cardEntranceAggressive,
  hoverLiftSubtle,
  createHoverLiftGlow,
  pageTransitionFade,
  pageTransitionSlide,
  pageTransitionInstant,
  pageTransitionScale,
  createStaggerContainer,
} from "./animations.ts"
export type { PageTransitionConfig } from "./animations.ts"

export { iceStation } from "./ice-station.ts"
export { warmOps } from "./warm-ops.ts"
export { stealth } from "./stealth.ts"
export { signal } from "./signal.ts"
export { neon } from "./neon.ts"

export { ThemeProvider, useTheme } from "./provider.tsx"

// ---- Lookup maps ----

import type { ThemeConfig, VariationSlug } from "./types.ts"
import { iceStation } from "./ice-station.ts"
import { warmOps } from "./warm-ops.ts"
import { stealth } from "./stealth.ts"
import { signal } from "./signal.ts"
import { neon } from "./neon.ts"

/** Map from variation slug (a-e) to its ThemeConfig */
export const themes: Record<VariationSlug, ThemeConfig> = {
  a: iceStation,
  b: warmOps,
  c: stealth,
  d: signal,
  e: neon,
}

/** All themes as an ordered array */
export const themeList: ThemeConfig[] = [
  iceStation,
  warmOps,
  stealth,
  signal,
  neon,
]
