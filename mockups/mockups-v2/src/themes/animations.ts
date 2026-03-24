import type { Variants, Transition, TargetAndTransition } from "framer-motion"

// ---------------------------------------------------------------------------
// Card entrance variants by animation profile
// ---------------------------------------------------------------------------

/** Minimal: simple opacity fade, no movement */
export const cardEntranceMinimal: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { duration: 0.2, ease: "easeOut" },
  },
}

/** Spring: opacity + vertical slide with spring physics */
export const cardEntranceSpring: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { type: "spring", stiffness: 300, damping: 25 },
  },
}

/** Instant: no animation at all */
export const cardEntranceInstant: Variants = {
  hidden: { opacity: 1 },
  visible: { opacity: 1 },
}

/** Status-driven: static entrance (animation only on state changes) */
export const cardEntranceStatusDriven: Variants = {
  hidden: { opacity: 1 },
  visible: { opacity: 1 },
}

/** Aggressive: opacity + vertical slide + scale with stagger */
export const cardEntranceAggressive: Variants = {
  hidden: { opacity: 0, y: 16, scale: 0.97 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { type: "spring", stiffness: 400, damping: 20 },
  },
}

// ---------------------------------------------------------------------------
// Hover lift variants
// ---------------------------------------------------------------------------

/** Subtle hover lift (warm-ops style) */
export const hoverLiftSubtle: TargetAndTransition = {
  scale: 1.01,
  transition: { type: "spring", stiffness: 300, damping: 25 },
}

/** Aggressive hover lift with glow shadow (neon style) */
export function createHoverLiftGlow(accentGlow: string): TargetAndTransition {
  return {
    scale: 1.02,
    boxShadow: `0 4px 24px ${accentGlow}`,
    transition: { type: "spring", stiffness: 400, damping: 20 },
  }
}

// ---------------------------------------------------------------------------
// Page transition presets
// ---------------------------------------------------------------------------

export interface PageTransitionConfig {
  initial: object
  animate: object
  exit: object
  transition?: Transition
}

export const pageTransitionFade: PageTransitionConfig = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
  transition: { duration: 0.15 },
}

export const pageTransitionSlide: PageTransitionConfig = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { type: "spring", stiffness: 300, damping: 25 },
}

export const pageTransitionInstant: PageTransitionConfig = {
  initial: { opacity: 1 },
  animate: { opacity: 1 },
  exit: { opacity: 1 },
}

export const pageTransitionScale: PageTransitionConfig = {
  initial: { opacity: 0, scale: 0.98 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.98 },
  transition: { type: "spring", stiffness: 400, damping: 20 },
}

// ---------------------------------------------------------------------------
// Stagger container variant factory
// ---------------------------------------------------------------------------

export function createStaggerContainer(
  staggerChildren: number,
): Variants {
  return {
    hidden: {},
    visible: {
      transition: {
        staggerChildren,
      },
    },
  }
}
