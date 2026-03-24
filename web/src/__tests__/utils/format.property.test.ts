import fc from 'fast-check'
import { formatCurrency, formatUptime, formatLabel, formatDate } from '@/utils/format'

describe('format property tests', () => {
  it('formatCurrency always contains $', () => {
    fc.assert(
      fc.property(
        fc.double({ min: -1e9, max: 1e9, noNaN: true }),
        (value) => {
          expect(formatCurrency(value)).toContain('$')
        },
      ),
    )
  })

  it('formatUptime always returns a non-empty string', () => {
    fc.assert(
      fc.property(fc.double({ min: -1e6, max: 1e9 }), (seconds) => {
        const result = formatUptime(seconds)
        expect(result.length).toBeGreaterThan(0)
      }),
    )
  })

  it('formatLabel preserves word count for snake_case inputs', () => {
    fc.assert(
      fc.property(
        fc.array(fc.stringMatching(/^[a-z]+$/), { minLength: 1, maxLength: 5 }),
        (words) => {
          const input = words.join('_')
          const result = formatLabel(input)
          expect(result.split(' ')).toHaveLength(words.length)
        },
      ),
    )
  })

  it('formatDate returns -- for any falsy input', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(null, undefined, ''),
        (input) => {
          expect(formatDate(input as string | null | undefined)).toBe('--')
        },
      ),
    )
  })
})
