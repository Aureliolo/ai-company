import fc from 'fast-check'
import { getPasswordStrength } from '@/utils/password-strength'

describe('getPasswordStrength', () => {
  it('returns empty for empty string', () => {
    const result = getPasswordStrength('')
    expect(result.label).toBe('')
    expect(result.percent).toBe(0)
  })

  it('returns Weak for very short passwords', () => {
    expect(getPasswordStrength('abc')).toMatchObject({ label: 'Weak', percent: 20 })
    expect(getPasswordStrength('1234567')).toMatchObject({ label: 'Weak', percent: 20 })
  })

  it('returns Fair for 8-11 character passwords', () => {
    expect(getPasswordStrength('abcdefgh')).toMatchObject({ label: 'Fair', percent: 40 })
    expect(getPasswordStrength('12345678901')).toMatchObject({ label: 'Fair', percent: 40 })
  })

  it('returns Fair for 12+ chars with low variety', () => {
    expect(getPasswordStrength('aaaaaaaaaaaa')).toMatchObject({ label: 'Fair', percent: 50 })
    expect(getPasswordStrength('abcdefghijkl')).toMatchObject({ label: 'Fair', percent: 50 })
  })

  it('returns Good for 12+ chars with 3+ character types', () => {
    expect(getPasswordStrength('Abcdefgh1234')).toMatchObject({ label: 'Good', percent: 75 })
    expect(getPasswordStrength('Password123!')).toMatchObject({ label: 'Good', percent: 75 })
  })

  it('returns Strong for 16+ chars with 3+ character types', () => {
    expect(getPasswordStrength('MyStr0ngPassword!')).toMatchObject({ label: 'Strong', percent: 100 })
    expect(getPasswordStrength('Abcdefgh12345678')).toMatchObject({ label: 'Strong', percent: 100 })
  })

  it('percent never exceeds 100', () => {
    fc.assert(
      fc.property(fc.string(), (pw) => {
        const result = getPasswordStrength(pw)
        expect(result.percent).toBeGreaterThanOrEqual(0)
        expect(result.percent).toBeLessThanOrEqual(100)
      }),
    )
  })

  it('always returns a color string', () => {
    fc.assert(
      fc.property(fc.string(), (pw) => {
        const result = getPasswordStrength(pw)
        expect(result.color).toMatch(/^bg-/)
      }),
    )
  })
})
