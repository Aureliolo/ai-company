import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Standard focus indicator classes per design spec:
 * 2px solid ring, 2px offset, accent color, :focus-visible only.
 */
export const FOCUS_RING =
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background'

/**
 * Runtime operational status for UI display.
 *
 * Distinct from the API-layer AgentStatus (api/types.ts) which represents
 * HR lifecycle state (active/onboarding/on_leave/terminated). A mapping
 * function should convert between the two at the data-binding boundary.
 */
export type AgentRuntimeStatus = "active" | "idle" | "error" | "offline"

/** Semantic color token names matching Tailwind utilities (e.g. `text-success`, `bg-danger`). */
export type SemanticColor = "success" | "accent" | "warning" | "danger"

const STATUS_COLOR_MAP: Record<AgentRuntimeStatus, SemanticColor | "text-secondary"> = {
  active: "success",
  idle: "accent",
  error: "danger",
  offline: "text-secondary",
}

/** Map a runtime agent status to its semantic color token name. */
export function getStatusColor(status: AgentRuntimeStatus): SemanticColor | "text-secondary" {
  return STATUS_COLOR_MAP[status]
}


/**
 * Map a 0-100 percentage to a semantic color token name.
 *
 * Thresholds: >=75 success, >=50 accent, >=25 warning, <25 danger.
 */
export function getHealthColor(percentage: number): SemanticColor {
  if (percentage >= 75) return "success"
  if (percentage >= 50) return "accent"
  if (percentage >= 25) return "warning"
  return "danger"
}
