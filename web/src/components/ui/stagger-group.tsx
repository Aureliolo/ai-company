import { motion } from 'framer-motion'
import { cardEntrance } from '@/lib/motion'
import { cn } from '@/lib/utils'

interface StaggerGroupProps {
  children?: React.ReactNode
  className?: string
  /** Stagger delay between children in seconds (default: 0.03). */
  staggerDelay?: number
  /** Whether to animate on mount (default: true). */
  animate?: boolean
}

interface StaggerItemProps {
  children: React.ReactNode
  className?: string
  /** Framer Motion layoutId for reorder animations. */
  layoutId?: string
  /** Enable layout animation for smooth size changes. */
  layout?: boolean
  'data-testid'?: string
}

/**
 * Container that staggers its children's entrance animations.
 *
 * Use with `StaggerItem` children for coordinated card entrance effects.
 * Limits stagger to ~10 items (300ms) to avoid long entrance sequences.
 */
export function StaggerGroup({
  children,
  className,
  staggerDelay = 0.03,
  animate = true,
}: StaggerGroupProps) {
  const containerVariants = {
    hidden: {},
    visible: {
      transition: {
        staggerChildren: staggerDelay,
        delayChildren: 0,
      },
    },
  }

  return (
    <motion.div
      variants={containerVariants}
      initial={animate ? 'hidden' : false}
      animate={animate ? 'visible' : false}
      className={className}
    >
      {children}
    </motion.div>
  )
}

/**
 * Individual item within a StaggerGroup.
 *
 * Applies the cardEntrance animation variant (fade up from 8px below).
 * Supports Framer Motion layout animations for smooth reordering.
 */
export function StaggerItem({
  children,
  className,
  layoutId,
  layout,
  'data-testid': testId,
}: StaggerItemProps) {
  return (
    <motion.div
      variants={cardEntrance}
      layoutId={layoutId}
      layout={layout}
      className={cn(className)}
      data-testid={testId}
    >
      {children}
    </motion.div>
  )
}
