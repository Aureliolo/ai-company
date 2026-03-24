/**
 * Framer Motion animation presets for the SynthOrg dashboard.
 *
 * Import these constants instead of hardcoding animation values in components.
 * See docs/design/ux-guidelines.md Section 4 for the full animation language.
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

import type { Transition, Variants } from "framer-motion";

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

/** Fast tween: micro-interactions, button press feedback. */
export const tweenFast: Transition = {
  type: "tween",
  duration: 0.15,
  ease: "easeOut",
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

/** Parent container that staggers children by 30ms, max 300ms total. */
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
    transition: { type: "tween", duration: 0.15, ease: "easeIn" },
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
 * Apply as a CSS class or inline style -- not a Framer Motion variant,
 * because the flash triggers on data change, not mount/unmount.
 *
 * Implementation pattern:
 * ```tsx
 * const [flash, setFlash] = useState(false);
 * useEffect(() => { setFlash(true); const t = setTimeout(() => setFlash(false), 600); return () => clearTimeout(t); }, [value]);
 * ```
 */
export const STATUS_FLASH_DURATION_MS = 600;

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

/**
 * Check if the user prefers reduced motion.
 *
 * Use this to conditionally disable or simplify animations:
 * ```tsx
 * const transition = prefersReducedMotion() ? tweenFast : springDefault;
 * ```
 */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
