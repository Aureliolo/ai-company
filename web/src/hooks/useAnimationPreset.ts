import { useMemo } from 'react'
import type { Transition } from 'framer-motion'
import {
  springDefault,
  springBouncy,
  tweenDefault,
  tweenFast,
  reducedMotionInstant,
} from '@/lib/motion'
import { useThemeStore } from '@/stores/theme'
import type { AnimationPreset } from '@/stores/theme'

export interface AnimationPresetConfig {
  /** Primary transition for modals, panels, card interactions (may be spring or tween depending on preset). */
  readonly spring: Transition
  /** Tween transition for hover states, color changes, opacity. */
  readonly tween: Transition
  /** Stagger delay between child animations (seconds). */
  readonly staggerDelay: number
  /** Whether to enable layout animations. */
  readonly enableLayout: boolean
}

const PRESET_CONFIGS: Record<AnimationPreset, AnimationPresetConfig> = {
  minimal: {
    spring: { ...tweenFast },
    tween: { type: 'tween', duration: 0.15, ease: 'easeOut' },
    staggerDelay: 0,
    enableLayout: false,
  },
  spring: {
    spring: springDefault,
    tween: tweenDefault,
    staggerDelay: 0.03,
    enableLayout: true,
  },
  instant: {
    spring: reducedMotionInstant,
    tween: reducedMotionInstant,
    staggerDelay: 0,
    enableLayout: false,
  },
  'status-driven': {
    spring: tweenDefault,
    tween: tweenDefault,
    staggerDelay: 0.02,
    enableLayout: true,
  },
  aggressive: {
    spring: springBouncy,
    tween: tweenDefault,
    staggerDelay: 0.05,
    enableLayout: true,
  },
}

/**
 * Returns animation configuration based on the user's theme animation preference.
 *
 * Components that want to respect the animation preference import this hook
 * instead of directly using lib/motion.ts constants. Existing components
 * continue to work unchanged -- this is a progressive enhancement.
 */
export function useAnimationPreset(): AnimationPresetConfig {
  const animation = useThemeStore((s) => s.animation)
  return useMemo(() => PRESET_CONFIGS[animation], [animation])
}
