/** Unicode BIDI override and direction control ranges that can manipulate log display. */
function isBidiControl(code: number): boolean {
  return (code >= 0x200b && code <= 0x200f)
    || (code >= 0x202a && code <= 0x202e)
    || (code >= 0x2066 && code <= 0x2069)
    || (code >= 0xfff9 && code <= 0xfffb)
}

/** Sanitize a value for safe logging (strip control chars + BIDI overrides, truncate). */
export function sanitizeForLog(value: unknown, maxLen = 500): string {
  const raw = value instanceof Error
    ? (value.stack ?? value.message ?? String(value))
    : String(value)
  let result = ''
  for (const ch of raw) {
    const code = ch.charCodeAt(0)
    result += (code >= 0x20 && code !== 0x7f && !isBidiControl(code)) ? ch : ' '
    if (result.length >= maxLen) break
  }
  return result
}
