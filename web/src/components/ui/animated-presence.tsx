import type { Variants } from 'framer-motion'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { reducedPageVariants } from '@/lib/motion'
import { cn } from '@/lib/utils'

export interface AnimatedPresenceProps {
  children: React.ReactNode
  /** Unique key for AnimatePresence tracking (typically location.pathname). */
  routeKey: string
  className?: string
}

/** Combined page transition variants for normal motion. */
const pageVariants: Variants = {
  initial: { opacity: 0, x: 8 },
  animate: {
    opacity: 1,
    x: 0,
    transition: { type: 'tween', duration: 0.2, ease: [0.4, 0, 0.2, 1] },
  },
  exit: {
    opacity: 0,
    x: -8,
    transition: { type: 'tween', duration: 0.15, ease: 'easeIn' },
  },
}

/**
 * Page transition wrapper using Framer Motion's AnimatePresence.
 *
 * Wraps children with enter/exit animations keyed by `routeKey`.
 * Automatically falls back to reduced-motion variants when the user
 * has `prefers-reduced-motion: reduce` enabled.
 */
export function AnimatedPresence({
  children,
  routeKey,
  className,
}: AnimatedPresenceProps) {
  const shouldReduceMotion = useReducedMotion()
  const variants = shouldReduceMotion ? reducedPageVariants : pageVariants

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={routeKey}
        variants={variants}
        initial="initial"
        animate="animate"
        exit="exit"
        className={cn('flex-1', className)}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  )
}
