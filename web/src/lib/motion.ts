/**
 * Motion animation presets for the SynthOrg dashboard.
 *
 * Import these constants instead of hardcoding animation values in components.
 * See docs/design/ux-guidelines.md (Animation Language section) for the full animation language.
 *
 * @example
 * ```tsx
 * import { springDefault, cardEntrance, staggerChildren } from "@/lib/motion";
 *
 * <motion.div
 *   variants={staggerChildren}
 *   initial="hidden"
 *   animate="visible"
 * >
 *   <motion.div variants={cardEntrance}>Card 1</motion.div>
 *   <motion.div variants={cardEntrance}>Card 2</motion.div>
 * </motion.div>
 * ```
 */

import type { Transition, Variants } from "motion/react";

// ---------------------------------------------------------------------------
// Spring presets
// ---------------------------------------------------------------------------

/** General-purpose spring: modals, panels, card interactions. */
export const springDefault: Transition = {
  type: "spring",
  stiffness: 300,
  damping: 30,
  mass: 1,
};

/** Subtle movements: tooltips, dropdowns, popovers. */
export const springGentle: Transition = {
  type: "spring",
  stiffness: 200,
  damping: 25,
  mass: 1,
};

/** Playful feedback: drag-drop settle, success confirmations. */
export const springBouncy: Transition = {
  type: "spring",
  stiffness: 400,
  damping: 20,
  mass: 0.8,
};

/** Snappy responses: toggles, switches, quick state changes. */
export const springStiff: Transition = {
  type: "spring",
  stiffness: 500,
  damping: 35,
  mass: 1,
};

// ---------------------------------------------------------------------------
// Tween presets
// ---------------------------------------------------------------------------

/** Default tween: hover states, color changes, opacity transitions. */
export const tweenDefault: Transition = {
  type: "tween",
  duration: 0.2,
  ease: [0.4, 0, 0.2, 1],
};

/** Slow tween: page transitions, large layout shifts. */
export const tweenSlow: Transition = {
  type: "tween",
  duration: 0.4,
  ease: [0.4, 0, 0.2, 1],
};

/** Slow tween duration in milliseconds (matches tweenSlow.duration). */
export const TRANSITION_SLOW_MS = 400;

/** Fast tween: micro-interactions, button press feedback. */
export const tweenFast: Transition = {
  type: "tween",
  duration: 0.15,
  ease: "easeOut",
};

/** Fast exit tween: panel/drawer exit, collapse animations (easeIn accelerates out of view). */
export const tweenExitFast: Transition = {
  type: "tween",
  duration: 0.15,
  ease: "easeIn",
};

/** Crossfade enter tween: fast opacity-only page transition enter (120ms easeOut). */
export const tweenCrossfadeEnter: Transition = {
  type: "tween" as const,
  duration: 0.12,
  ease: "easeOut" as const,
};

/** Crossfade exit tween: very fast opacity-only page transition exit (60ms easeIn). */
export const tweenCrossfadeExit: Transition = {
  type: "tween" as const,
  duration: 0.06,
  ease: "easeIn" as const,
};

// ---------------------------------------------------------------------------
// Card entrance variants
// ---------------------------------------------------------------------------

/** Card entrance: fade up from 8px below. Use with staggerChildren. */
export const cardEntrance: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: {
    opacity: 1,
    y: 0,
    transition: tweenDefault,
  },
};

/**
 * Parent container that staggers children by 30ms.
 *
 * Note: Motion does not enforce a stagger cap. Consuming components
 * should limit visible stagger to ~10 items (300ms) to avoid long entrance
 * sequences -- e.g. by paginating or virtualizing beyond that threshold.
 */
export const staggerChildren: Variants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.03,
      delayChildren: 0,
    },
  },
};

// ---------------------------------------------------------------------------
// Page transitions
// ---------------------------------------------------------------------------

/** Page exit: fade out + slide left. */
export const pageExit: Variants = {
  initial: { opacity: 1, x: 0 },
  exit: {
    opacity: 0,
    x: -8,
    transition: tweenExitFast,
  },
};

/** Page enter: fade in + slide from right. */
export const pageEnter: Variants = {
  initial: { opacity: 0, x: 8 },
  animate: {
    opacity: 1,
    x: 0,
    transition: tweenDefault,
  },
};

// ---------------------------------------------------------------------------
// Status change flash
// ---------------------------------------------------------------------------

/**
 * Flash effect for real-time value updates.
 *
 * Three-phase animation: flash (200ms) -> hold (100ms) -> fade (300ms).
 * Apply via CSS `@keyframes` or inline style -- not a Motion variant,
 * because the flash triggers on data change, not mount/unmount.
 *
 * Recommended CSS implementation (actual keyframe is `so-status-flash` in `design-tokens.css`):
 * ```css
 * \@keyframes so-status-flash {
 *   0%   { background-color: var(--so-overlay-flash); }
 *   33%  { background-color: var(--so-overlay-flash); }  // hold
 *   50%  { background-color: var(--so-overlay-flash); }  // hold end
 *   100% { background-color: transparent; }               // fade
 * }
 * ```
 */
const _FLASH_MS = 200;
const _HOLD_MS = 100;
const _FADE_MS = 300;

export const STATUS_FLASH = {
  flashMs: _FLASH_MS,
  holdMs: _HOLD_MS,
  fadeMs: _FADE_MS,
  totalMs: _FLASH_MS + _HOLD_MS + _FADE_MS,
} as const;

// ---------------------------------------------------------------------------
// Toast animations
// ---------------------------------------------------------------------------

/** Toast entrance: slide up from 16px below with spring settle. */
export const toastEntrance: Variants = {
  initial: { opacity: 0, y: 16, scale: 0.95 },
  animate: { opacity: 1, y: 0, scale: 1, transition: springDefault },
  exit: { opacity: 0, x: 80, transition: tweenFast },
};

// ---------------------------------------------------------------------------
// Modal / overlay animations
// ---------------------------------------------------------------------------

/** Overlay backdrop: simple opacity fade. */
export const overlayBackdrop: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: tweenDefault },
  exit: { opacity: 0, transition: tweenFast },
};

/** Modal/dialog entrance: scale up with spring + fade. */
export const modalEntrance: Variants = {
  initial: { opacity: 0, scale: 0.95, y: 8 },
  animate: { opacity: 1, scale: 1, y: 0, transition: springDefault },
  exit: { opacity: 0, scale: 0.95, y: 8, transition: tweenFast },
};

// ---------------------------------------------------------------------------
// List reorder
// ---------------------------------------------------------------------------

/** List item enter/exit for AnimatePresence + layout animations. */
export const listItemLayout: Variants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: tweenDefault },
  exit: { opacity: 0, y: -8, transition: tweenFast },
};

// ---------------------------------------------------------------------------
// Inline edit
// ---------------------------------------------------------------------------

/** Inline edit field entrance: subtle fade-in. */
export const inlineEditEntrance: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: springGentle },
  exit: { opacity: 0, transition: tweenFast },
};

// ---------------------------------------------------------------------------
// Status color transition
// ---------------------------------------------------------------------------

/** Tween for animating between status colors (e.g. active -> error). */
export const statusColorTransition: Transition = {
  type: "tween",
  duration: 0.3,
  ease: [0.4, 0, 0.2, 1],
};

// ---------------------------------------------------------------------------
// Reduced page variants
// ---------------------------------------------------------------------------

/** Page transition for reduced-motion: opacity-only fade, no slide. */
export const reducedPageVariants: Variants = {
  initial: { opacity: 0 },
  animate: {
    opacity: 1,
    transition: { type: "tween", duration: 0.15, ease: "easeOut" },
  },
  exit: {
    opacity: 0,
    transition: { type: "tween", duration: 0.1, ease: "easeIn" },
  },
};

// ---------------------------------------------------------------------------
// Badge bounce
// ---------------------------------------------------------------------------

/** Badge count increment: scale bounce 1.0 -> 1.15 -> 1.0. */
export const badgeBounce: Variants = {
  initial: { scale: 1 },
  bounce: {
    scale: [1, 1.15, 1],
    transition: springDefault,
  },
};

// ---------------------------------------------------------------------------
// Reduced motion
// ---------------------------------------------------------------------------

/** Instant transition for reduced-motion contexts (springs become instant). */
export const reducedMotionInstant: Transition = {
  duration: 0,
};

/**
 * Check if the user prefers reduced motion (point-in-time snapshot).
 *
 * For reactive detection that responds to OS preference changes mid-session,
 * use Motion's built-in `useReducedMotion()` hook or write a custom
 * hook with `matchMedia("(prefers-reduced-motion: reduce)")` + change listener.
 *
 * This utility is for non-React contexts (e.g. SSR branching, one-time checks):
 * ```tsx
 * const transition = prefersReducedMotion() ? reducedMotionInstant : springDefault;
 * ```
 */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
