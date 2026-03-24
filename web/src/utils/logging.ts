/** Unicode BIDI override and direction control ranges that can manipulate log display. */
function isBidiControl(code: number): boolean {
  return (code >= 0x200b && code <= 0x200f)
    || (code >= 0x202a && code <= 0x202e)
    || (code >= 0x2066 && code <= 0x2069)
    || (code >= 0xfff9 && code <= 0xfffb)
}

/** Sanitize a value for safe logging (strip control chars + BIDI overrides, truncate). */
export function sanitizeForLog(value: unknown, maxLen = 500): string {
  const cap = Number.isFinite(maxLen) ? Math.max(0, Math.floor(maxLen)) : 500
  if (cap === 0) return ''
  let raw: string
  if (value instanceof Error) {
    raw = value.stack ?? value.message ?? String(value)
  } else {
    try {
      raw = String(value)
    } catch {
      raw = '[unstringifiable]'
    }
  }
  let result = ''
  for (const ch of raw) {
    const code = ch.codePointAt(0) ?? 0
    const isControl = code < 0x20 || code === 0x7f || (code >= 0x80 && code <= 0x9f)
    result += (!isControl && !isBidiControl(code)) ? ch : ' '
    if (result.length >= cap) break
  }
  return result
}
