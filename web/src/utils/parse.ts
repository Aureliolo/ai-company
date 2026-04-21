/**
 * Shared JSON-parse narrowers.
 *
 * Centralises the "narrow this ``unknown`` to a plain object record"
 * check so stores and utilities don't duplicate the `typeof === 'object'`
 * + not-null + not-array gate. Returns ``null`` on non-object inputs so
 * callers can fall through to a default.
 */

/**
 * Narrow a ``JSON.parse`` result (or similarly untyped value) to a
 * keyed object. Returns ``null`` for non-objects, ``null`` itself, and
 * arrays -- any of which would otherwise satisfy ``typeof === 'object'``.
 */
export function asObjectRecord(value: unknown): Record<string, unknown> | null {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return null
  }
  return value as Record<string, unknown>
}

/**
 * Narrow a value to an array of object records. Non-array inputs and
 * non-object items are skipped; the result is always an array (empty
 * when the input isn't one).
 */
export function asObjectRecordArray(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) return []
  const out: Record<string, unknown>[] = []
  for (const item of value) {
    const narrowed = asObjectRecord(item)
    if (narrowed) out.push(narrowed)
  }
  return out
}
