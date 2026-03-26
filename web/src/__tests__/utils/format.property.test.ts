import fc from 'fast-check'
import { formatCurrency, formatUptime, formatLabel, formatDate } from '@/utils/format'

describe('format property tests', () => {
  it('formatCurrency with USD always contains $', () => {
    fc.assert(
      fc.property(
        fc.double({ min: -1e9, max: 1e9, noNaN: true }),
        (value) => {
          expect(formatCurrency(value, 'USD')).toContain('$')
        },
      ),
    )
  })

  it('formatCurrency with EUR always contains euro sign', () => {
    fc.assert(
      fc.property(
        fc.double({ min: -1e9, max: 1e9, noNaN: true }),
        (value) => {
          expect(formatCurrency(value, 'EUR')).toContain('\u20ac')
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

  it('formatCurrency with no currencyCode defaults to EUR', () => {
    fc.assert(
      fc.property(
        fc.double({ min: -1e9, max: 1e9, noNaN: true }),
        (value) => {
          expect(formatCurrency(value)).toContain('\u20ac')
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
