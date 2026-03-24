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

  it('never contains control characters', () => {
    fc.assert(
      fc.property(fc.string(), (input) => {
        const result = sanitizeForLog(input)
        for (const ch of result) {
          const code = ch.charCodeAt(0)
          expect(code).toBeGreaterThanOrEqual(0x20)
          expect(code).not.toBe(0x7f)
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
