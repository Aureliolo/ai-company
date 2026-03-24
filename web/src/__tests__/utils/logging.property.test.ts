import fc from 'fast-check'
import { sanitizeForLog } from '@/utils/logging'

describe('sanitizeForLog property tests', () => {
  it('never exceeds maxLen', () => {
    fc.assert(
      fc.property(fc.string(), fc.integer({ min: 1, max: 2000 }), (input, maxLen) => {
        const result = sanitizeForLog(input, maxLen)
        expect(result.length).toBeLessThanOrEqual(maxLen)
      }),
    )
  })

  it('never contains control or BIDI characters', () => {
    const bidiControls = new Set([
      0x200b, 0x200c, 0x200d, 0x200e, 0x200f,
      0x202a, 0x202b, 0x202c, 0x202d, 0x202e,
      0x2066, 0x2067, 0x2068, 0x2069,
      0xfff9, 0xfffa, 0xfffb,
    ])
    fc.assert(
      fc.property(fc.string(), (input) => {
        const result = sanitizeForLog(input)
        for (const ch of result) {
          const code = ch.codePointAt(0) ?? 0
          expect(code).toBeGreaterThanOrEqual(0x20)
          expect(code).not.toBe(0x7f)
          // C1 controls
          expect(code < 0x80 || code > 0x9f).toBe(true)
          // BIDI overrides
          expect(bidiControls.has(code)).toBe(false)
        }
      }),
    )
  })

  it('returns a string for any input type', () => {
    fc.assert(
      fc.property(fc.anything(), (input) => {
        expect(typeof sanitizeForLog(input)).toBe('string')
      }),
    )
  })
})
