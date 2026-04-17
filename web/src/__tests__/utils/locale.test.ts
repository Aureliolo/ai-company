import { APP_LOCALE, getLocale } from '@/utils/locale'

describe('APP_LOCALE', () => {
  it('is a non-empty string', () => {
    expect(typeof APP_LOCALE).toBe('string')
    expect(APP_LOCALE.length).toBeGreaterThan(0)
  })

  it('matches IETF BCP 47 language-region shape', () => {
    expect(APP_LOCALE).toMatch(/^[a-z]{2}-[A-Z]{2}$/)
  })

  it('is a valid Intl locale', () => {
    expect(() => new Intl.Locale(APP_LOCALE)).not.toThrow()
  })

  it.each(['en_US', 'en-us', 'EN-US', 'en', ''])(
    'rejects the malformed candidate %j against the BCP 47 shape regex',
    (candidate) => {
      expect(candidate).not.toMatch(/^[a-z]{2}-[A-Z]{2}$/)
    },
  )
})

describe('getLocale', () => {
  it('returns a string', () => {
    expect(typeof getLocale()).toBe('string')
  })

  it('defaults to APP_LOCALE when no override is configured', () => {
    expect(getLocale()).toBe(APP_LOCALE)
  })

  it('returns a value usable by Intl APIs', () => {
    const locale = getLocale()
    expect(() =>
      new Intl.NumberFormat(locale).format(1000),
    ).not.toThrow()
    expect(() =>
      new Intl.DateTimeFormat(locale).format(new Date()),
    ).not.toThrow()
  })
})
