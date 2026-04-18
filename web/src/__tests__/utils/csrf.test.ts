import { getCsrfToken } from '@/utils/csrf'

/**
 * Direct unit tests for the cookie-parsing path in `getCsrfToken`.
 *
 * The CSRF interceptor tests in `__tests__/api/client.test.ts` mock
 * `getCsrfToken` to avoid jsdom's tough-cookie Promise leak when
 * `document.cookie` is mutated. That leaves the cookie-parsing logic
 * itself untested, so these tests exercise it directly by swapping
 * `document.cookie` with a property-descriptor override -- no actual
 * jsdom cookie-jar writes, no leaks.
 */
describe('getCsrfToken', () => {
  let originalDescriptor: PropertyDescriptor | undefined

  beforeAll(() => {
    originalDescriptor = Object.getOwnPropertyDescriptor(
      Document.prototype,
      'cookie',
    )
  })

  afterEach(() => {
    if (originalDescriptor) {
      Object.defineProperty(Document.prototype, 'cookie', originalDescriptor)
    }
  })

  function mockCookie(value: string): void {
    Object.defineProperty(Document.prototype, 'cookie', {
      configurable: true,
      get: () => value,
    })
  }

  it('returns the token when csrf_token cookie is present', () => {
    mockCookie('session=abc; csrf_token=xyz123; path=/')
    expect(getCsrfToken()).toBe('xyz123')
  })

  it('returns the token when it is the only cookie', () => {
    mockCookie('csrf_token=only-one')
    expect(getCsrfToken()).toBe('only-one')
  })

  it('returns null when cookie jar is empty', () => {
    mockCookie('')
    expect(getCsrfToken()).toBeNull()
  })

  it('returns null when csrf_token cookie is absent', () => {
    mockCookie('session=abc; other=value')
    expect(getCsrfToken()).toBeNull()
  })

  it('trims surrounding whitespace around cookie entries', () => {
    mockCookie('session=abc ;  csrf_token=spaced ; path=/')
    expect(getCsrfToken()).toBe('spaced')
  })

  it('decodes URL-encoded token values', () => {
    mockCookie('csrf_token=a%2Fb%3Fc%3Dd')
    expect(getCsrfToken()).toBe('a/b?c=d')
  })

  it('returns null on malformed URL-encoded token', () => {
    mockCookie('csrf_token=%FF%FF')
    expect(getCsrfToken()).toBeNull()
  })

  it('returns empty string when token value is empty (indexOf returns valid position)', () => {
    mockCookie('csrf_token=')
    expect(getCsrfToken()).toBe('')
  })

  it('does not match a cookie whose name is a superstring of csrf_token', () => {
    // ``csrf_token_other`` should not be treated as ``csrf_token``; the
    // `startsWith('csrf_token=')` check enforces an exact-name match.
    mockCookie('csrf_token_other=wrong; other=value')
    expect(getCsrfToken()).toBeNull()
  })
})
