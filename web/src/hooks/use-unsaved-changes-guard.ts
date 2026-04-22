import { useCallback, useEffect, useRef, useState } from 'react'
import { useBlocker } from 'react-router'
import { createLogger } from '@/lib/logger'
import { sanitizeForLog } from '@/utils/logging'

const log = createLogger('unsaved-changes-guard')

export interface UseUnsavedChangesGuardOptions {
  /** Whether the form is dirty (has unsaved changes). */
  when: boolean
  /** Message shown in the ConfirmDialog. Default: "Discard unsaved changes?". */
  message?: string
  /** localStorage key for auto-save. Omit to disable draft persistence. */
  draftKey?: string
  /** Serializer invoked on every change (debounced) to produce the draft payload. */
  draftData?: () => unknown
  /**
   * Signal that the draft payload has changed so the debounced write effect
   * reschedules. Callers typically pass a JSON-serialized snapshot, a version
   * counter bumped on every edit, or the dirty form value itself. Omit to
   * schedule only once when `when` flips to true.
   */
  draftTrigger?: unknown
  /** Debounce interval for draft writes. Default 500ms. */
  draftDebounceMs?: number
  /** Callback when the user confirms "discard changes". Called after navigation proceeds. */
  onDiscard?: () => void
}

export interface UseUnsavedChangesGuardResult<T = unknown> {
  /** True when a confirmation dialog should be shown (navigation is pending). */
  confirmOpen: boolean
  /** Confirm discard -- allows the pending navigation to proceed. */
  proceed: () => void
  /** Cancel the discard -- keeps the user on the current page. */
  cancel: () => void
  /** Configured discard message (pass to ConfirmDialog as description). */
  message: string
  /** True when a draft exists in localStorage and has not been loaded/discarded yet. */
  hasDraft: boolean
  /** Read the persisted draft payload. Returns null if no draft. */
  restoreDraft: () => T | null
  /** Delete the persisted draft. Call after a successful save. */
  discardDraft: () => void
}

const DEFAULT_MESSAGE = 'Discard unsaved changes?'

function readDraft<T>(key: string | undefined): T | null {
  if (!key || typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) return null
    return JSON.parse(raw) as T
  } catch (err) {
    log.warn('failed to read draft', { key: sanitizeForLog(key) }, err)
    return null
  }
}

function writeDraft(key: string, data: unknown): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(key, JSON.stringify(data))
  } catch (err) {
    log.warn('failed to persist draft', { key: sanitizeForLog(key) }, err)
  }
}

function removeDraft(key: string): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.removeItem(key)
  } catch (err) {
    log.warn('failed to remove draft', { key: sanitizeForLog(key) }, err)
  }
}

/**
 * Intercept navigation while a form is dirty.
 *
 * Composes three layers:
 * 1. React Router `useBlocker` for in-app navigation
 * 2. `window.beforeunload` for tab close / reload
 * 3. (optional) localStorage draft persistence with debounced writes, exposing
 *    `hasDraft` + `restoreDraft` so the caller can offer draft restore on
 *    next visit.
 *
 * The caller is responsible for:
 * - Rendering a `<ConfirmDialog open={confirmOpen} onConfirm={proceed} onCancel={cancel} />`
 * - Calling `discardDraft()` after a successful save
 */
export function useUnsavedChangesGuard<T = unknown>({
  when,
  message = DEFAULT_MESSAGE,
  draftKey,
  draftData,
  draftTrigger,
  draftDebounceMs = 500,
  onDiscard,
}: UseUnsavedChangesGuardOptions): UseUnsavedChangesGuardResult<T> {
  const blocker = useBlocker(when)
  const confirmOpen = blocker.state === 'blocked'

  // ---- beforeunload (tab close / reload) ----
  useEffect(() => {
    if (!when) return
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      // Chrome requires returnValue to be set (legacy)
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [when])

  // ---- localStorage draft persistence ----
  const [hasDraft, setHasDraft] = useState<boolean>(() => {
    if (!draftKey || typeof window === 'undefined') return false
    return window.localStorage.getItem(draftKey) !== null
  })
  const draftTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const draftDataRef = useRef(draftData)
  draftDataRef.current = draftData

  // Refresh hasDraft whenever draftKey changes so callers see the correct
  // state after navigating between forms that share the hook.
  useEffect(() => {
    if (!draftKey || typeof window === 'undefined') {
      // eslint-disable-next-line @eslint-react/set-state-in-effect -- draftKey-driven reconciliation
      setHasDraft(false)
      return
    }
    // eslint-disable-next-line @eslint-react/set-state-in-effect -- draftKey-driven reconciliation
    setHasDraft(window.localStorage.getItem(draftKey) !== null)
  }, [draftKey])

  // Debounced draft persistence. The caller passes a `draftTrigger` value
  // (any serialisable marker derived from the form payload) that changes on
  // every edit; when it changes we reschedule the debounce so subsequent
  // edits also land in localStorage instead of only the first one.
  useEffect(() => {
    if (!draftKey || !draftDataRef.current) return
    if (!when) return

    if (draftTimerRef.current) clearTimeout(draftTimerRef.current)
    draftTimerRef.current = setTimeout(() => {
      const serializer = draftDataRef.current
      if (!serializer) return
      writeDraft(draftKey, serializer())
      setHasDraft(true)
      draftTimerRef.current = null
    }, draftDebounceMs)

    return () => {
      if (draftTimerRef.current) {
        clearTimeout(draftTimerRef.current)
        draftTimerRef.current = null
      }
    }
  }, [when, draftKey, draftDebounceMs, draftTrigger])

  const restoreDraft = useCallback<() => T | null>(() => {
    return readDraft<T>(draftKey)
  }, [draftKey])

  const discardDraft = useCallback(() => {
    if (!draftKey) return
    removeDraft(draftKey)
    setHasDraft(false)
  }, [draftKey])

  // ---- blocker proceed / cancel ----
  const proceed = useCallback(() => {
    if (blocker.state === 'blocked') {
      if (draftKey) {
        // User discarded changes; remove the draft so it doesn't confuse them next visit.
        removeDraft(draftKey)
        setHasDraft(false)
      }
      onDiscard?.()
      blocker.proceed()
    }
  }, [blocker, draftKey, onDiscard])

  const cancel = useCallback(() => {
    if (blocker.state === 'blocked') {
      blocker.reset()
    }
  }, [blocker])

  return {
    confirmOpen,
    proceed,
    cancel,
    message,
    hasDraft,
    restoreDraft,
    discardDraft,
  }
}
