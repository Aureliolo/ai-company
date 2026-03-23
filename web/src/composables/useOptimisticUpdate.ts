import { ref } from 'vue'
import { getErrorMessage } from '@/utils/errors'

/**
 * Perform an optimistic UI update with rollback on failure.
 *
 * Returns an `execute(applyOptimistic, serverAction)` function where
 * `applyOptimistic` applies the optimistic state and returns a rollback function,
 * and `serverAction` is the actual server request.
 *
 * A `null` return means one of two things:
 * - **Server error**: `error.value` is set with a message. The optimistic state was rolled back.
 * - **Already in-flight**: `pending.value` was true, so the call was a no-op. `error.value` is
 *   unchanged from its previous value (may be `null`).
 *
 * Callers should check `error.value` to distinguish server errors from no-op returns.
 */
export function useOptimisticUpdate() {
  const pending = ref(false)
  const error = ref<string | null>(null)

  async function execute<T>(
    applyOptimistic: () => () => void,
    serverAction: () => Promise<T>,
  ): Promise<T | null> {
    if (pending.value) return null
    pending.value = true
    error.value = null

    // Capture rollback before any mutation so a partial throw is still reversible
    let rollback: () => void
    try {
      rollback = applyOptimistic()
    } catch (prepareErr) {
      pending.value = false
      error.value = getErrorMessage(prepareErr)
      console.error('Optimistic prepare failed:', error.value)
      return null
    }

    try {
      const result = await serverAction()
      return result
    } catch (err) {
      let rollbackFailed = false
      try {
        rollback()
      } catch (rollbackErr) {
        rollbackFailed = true
        console.error('Rollback failed:', getErrorMessage(rollbackErr))
      }
      const base = getErrorMessage(err)
      error.value = rollbackFailed ? `${base} (UI may be out of sync -- please refresh)` : base
      console.error('Optimistic update failed:', error.value)
      return null
    } finally {
      pending.value = false
    }
  }

  return { pending, error, execute }
}
