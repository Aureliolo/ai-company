import { APP_LOCALE, APP_LOCALE_FALLBACK, getLocale } from '@/utils/locale'
import { useSettingsStore } from '@/stores/settings'

describe('APP_LOCALE_FALLBACK', () => {
  it('is plain "en" (neutral language, no region)', () => {
    // The fallback deliberately carries no region. "en-US" (or any
    // other language-region) would privilege one locale's date,
    // number, and unit defaults over others when no operator setting
    // and no browser tag are available. Plain "en" lets Intl pick
    // neutral defaults from the language subtag alone.
    expect(APP_LOCALE_FALLBACK).toBe('en')
    expect(APP_LOCALE).toBe(APP_LOCALE_FALLBACK)
  })

  it('canonicalizes to itself via Intl.getCanonicalLocales', () => {
    expect(Intl.getCanonicalLocales(APP_LOCALE_FALLBACK)).toEqual(['en'])
  })

  it('is a valid Intl locale', () => {
    expect(() => new Intl.Locale(APP_LOCALE_FALLBACK)).not.toThrow()
  })

  it.each([
    'en_US', // underscore instead of hyphen
    '', // empty string
    'not a locale', // whitespace in subtag
  ])('Intl rejects the malformed candidate %j', (candidate) => {
    expect(() => Intl.getCanonicalLocales(candidate)).toThrow()
  })
})

describe('getLocale', () => {
  beforeEach(() => {
    // Reset the locale override so each test starts from the
    // "browser or fallback" branch unless it opts in.
    useSettingsStore.setState({ locale: null })
  })

  it('returns a string', () => {
    expect(typeof getLocale()).toBe('string')
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

  it('prefers the settings-store override over the browser locale', () => {
    useSettingsStore.setState({ locale: 'de-CH' })
    expect(getLocale()).toBe('de-CH')
  })

  it('trims whitespace around the override', () => {
    useSettingsStore.setState({ locale: '  fr-FR  ' })
    expect(getLocale()).toBe('fr-FR')
  })

  it('ignores a blank override and falls through to browser/fallback', () => {
    useSettingsStore.setState({ locale: '   ' })
    // Falls through to navigator.language (or fallback in JSDOM).
    expect(getLocale()).not.toBe('   ')
    expect(getLocale().length).toBeGreaterThan(0)
  })

  it('ignores a malformed override and falls through', () => {
    // ``123!!!`` is syntactically invalid per BCP 47
    // (language subtag must be alpha); Intl.getCanonicalLocales
    // throws, so the override is discarded.
    useSettingsStore.setState({ locale: '123!!!' })
    expect(getLocale()).not.toBe('123!!!')
  })
})
