import { sanitizeForLog } from '@/utils/logging'

describe('sanitizeForLog', () => {
  it('returns string representation of primitives', () => {
    expect(sanitizeForLog('hello')).toBe('hello')
    expect(sanitizeForLog(42)).toBe('42')
    expect(sanitizeForLog(true)).toBe('true')
    expect(sanitizeForLog(null)).toBe('null')
    expect(sanitizeForLog(undefined)).toBe('undefined')
  })

  it('extracts Error stack (includes message)', () => {
    const result = sanitizeForLog(new Error('boom'))
    // Stack starts with "Error: boom" followed by stack frames
    expect(result).toContain('Error: boom')
    expect(result).toContain('at ')
  })

  it('strips control characters', () => {
    expect(sanitizeForLog('a\x00b\x01c\x1fd')).toBe('a b c d')
  })

  it('strips DEL character (0x7f)', () => {
    expect(sanitizeForLog('a\x7fb')).toBe('a b')
  })

  it('preserves printable ASCII and unicode', () => {
    expect(sanitizeForLog('Hello, World! 123')).toBe('Hello, World! 123')
    expect(sanitizeForLog('cafe')).toBe('cafe')
    expect(sanitizeForLog('caf\u00e9')).toBe('caf\u00e9')
    expect(sanitizeForLog('\u3053\u3093\u306b\u3061\u306f')).toBe('\u3053\u3093\u306b\u3061\u306f')
  })

  it('truncates at maxLen', () => {
    const long = 'a'.repeat(600)
    expect(sanitizeForLog(long)).toHaveLength(500)
    expect(sanitizeForLog(long, 10)).toHaveLength(10)
  })

  it('handles empty string', () => {
    expect(sanitizeForLog('')).toBe('')
  })

  it('handles objects via String()', () => {
    expect(sanitizeForLog({ key: 'value' })).toBe('[object Object]')
  })
})
