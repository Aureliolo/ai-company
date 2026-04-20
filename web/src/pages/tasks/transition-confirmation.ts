import type { TaskStatus } from '@/api/types/enums'

/** Statuses that require explicit confirmation before moving the task there. */
const CONFIRM_TRANSITIONS: readonly TaskStatus[] = ['completed', 'rejected', 'failed']

export function requiresTransitionConfirmation(status: TaskStatus): boolean {
  return CONFIRM_TRANSITIONS.includes(status)
}
