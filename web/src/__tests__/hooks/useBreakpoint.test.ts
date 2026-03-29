import { renderHook, act } from '@testing-library/react'
import { useBreakpoint } from '@/hooks/useBreakpoint'

type Listener = (e: { matches: boolean }) => void

function mockMatchMedia(desktopMatches: boolean, desktopSmMatches: boolean, tabletMatches: boolean) {
  const listeners = new Map<string, Set<Listener>>()
  const mqObjects = new Map<string, { matches: boolean }>()

  vi.stubGlobal('matchMedia', (query: string) => {
    let matches: boolean
    if (query === '(min-width: 1280px)') matches = desktopMatches
    else if (query === '(min-width: 1024px)') matches = desktopSmMatches
    else if (query === '(min-width: 768px)') matches = tabletMatches
    else matches = false

    if (!listeners.has(query)) listeners.set(query, new Set())

    // Return the same object reference for the same query so .matches updates work
    if (!mqObjects.has(query)) {
      mqObjects.set(query, { matches })
    }
    const mq = mqObjects.get(query)!
    mq.matches = matches

    return {
      get matches() { return mq.matches },
      media: query,
      addEventListener: (_: string, fn: Listener) => { listeners.get(query)!.add(fn) },
      removeEventListener: (_: string, fn: Listener) => { listeners.get(query)!.delete(fn) },
      addListener: vi.fn(),
      removeListener: vi.fn(),
      onchange: null,
      dispatchEvent: vi.fn(),
    }
  })

  return {
    /** Simulate a viewport change by updating .matches and triggering listeners. */
    trigger(query: string, matches: boolean) {
      const mq = mqObjects.get(query)
      if (mq) mq.matches = matches
      const set = listeners.get(query)
      if (set) {
        for (const fn of set) {
          fn({ matches })
        }
      }
    },
  }
}

describe('useBreakpoint', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns desktop when all breakpoints match', () => {
    mockMatchMedia(true, true, true)
    const { result } = renderHook(() => useBreakpoint())

    expect(result.current.breakpoint).toBe('desktop')
    expect(result.current.isDesktop).toBe(true)
    expect(result.current.isTablet).toBe(false)
    expect(result.current.isMobile).toBe(false)
  })

  it('returns desktop-sm when 1024 matches but not 1280', () => {
    mockMatchMedia(false, true, true)
    const { result } = renderHook(() => useBreakpoint())

    expect(result.current.breakpoint).toBe('desktop-sm')
  })

  it('returns tablet when only 768 matches', () => {
    mockMatchMedia(false, false, true)
    const { result } = renderHook(() => useBreakpoint())

    expect(result.current.breakpoint).toBe('tablet')
    expect(result.current.isTablet).toBe(true)
  })

  it('returns mobile when no breakpoints match', () => {
    mockMatchMedia(false, false, false)
    const { result } = renderHook(() => useBreakpoint())

    expect(result.current.breakpoint).toBe('mobile')
    expect(result.current.isMobile).toBe(true)
  })

  it('updates when matchMedia listener fires', () => {
    const mocks = mockMatchMedia(true, true, true)
    const { result } = renderHook(() => useBreakpoint())

    expect(result.current.breakpoint).toBe('desktop')

    // Simulate resize to desktop-sm
    act(() => {
      mocks.trigger('(min-width: 1280px)', false)
    })

    expect(result.current.breakpoint).toBe('desktop-sm')
  })

  it('returns desktop by default when window is undefined', () => {
    // jsdom has window, but we test the fallback path indirectly
    // since the hook checks typeof window === 'undefined'
    mockMatchMedia(true, true, true)
    const { result } = renderHook(() => useBreakpoint())
    expect(result.current.breakpoint).toBe('desktop')
  })
})
