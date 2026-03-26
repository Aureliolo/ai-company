import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export type AgentStatus = "active" | "idle" | "error" | "offline"

/** Semantic color token names matching Tailwind utilities (e.g. `text-success`, `bg-danger`). */
export type SemanticColor = "success" | "accent" | "warning" | "danger"

const STATUS_COLOR_MAP: Record<AgentStatus, SemanticColor | "text-secondary"> = {
  active: "success",
  idle: "accent",
  error: "danger",
  offline: "text-secondary",
}

/** Map an agent status to its semantic color token name. */
export function getStatusColor(status: AgentStatus): SemanticColor | "text-secondary" {
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
