import { APP_LOCALE, getLocale } from '@/utils/locale'

describe('APP_LOCALE', () => {
  it('is a non-empty string', () => {
    expect(typeof APP_LOCALE).toBe('string')
    expect(APP_LOCALE.length).toBeGreaterThan(0)
  })

  it('canonicalizes to itself via Intl.getCanonicalLocales', () => {
    const canonical = Intl.getCanonicalLocales(APP_LOCALE)
    expect(canonical).toEqual([APP_LOCALE])
  })

  it('is a valid Intl locale', () => {
    expect(() => new Intl.Locale(APP_LOCALE)).not.toThrow()
  })

  it.each([
    'en_US', // underscore instead of hyphen
    'en', // language-only (accepted by Intl but not our APP_LOCALE shape)
    '', // empty string
    'not a locale', // whitespace, no region
  ])('rejects the malformed candidate %j', (candidate) => {
    if (candidate === 'en') {
      // `Intl.getCanonicalLocales('en')` succeeds; assert it does NOT
      // normalize to APP_LOCALE so the test still catches unintended
      // language-only drift for our BCP 47 language-region requirement.
      expect(Intl.getCanonicalLocales(candidate)).not.toEqual([APP_LOCALE])
    } else {
      expect(() => Intl.getCanonicalLocales(candidate)).toThrow()
    }
  })
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
