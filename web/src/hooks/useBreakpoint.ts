import { useEffect, useState } from 'react'

export type Breakpoint = 'desktop' | 'desktop-sm' | 'tablet' | 'mobile'

interface UseBreakpointReturn {
  breakpoint: Breakpoint
  isDesktop: boolean
  isTablet: boolean
  isMobile: boolean
}

const QUERY_DESKTOP = '(min-width: 1280px)'
const QUERY_DESKTOP_SM = '(min-width: 1024px)'
const QUERY_TABLET = '(min-width: 768px)'

function resolve(desktop: boolean, desktopSm: boolean, tablet: boolean): Breakpoint {
  if (desktop) return 'desktop'
  if (desktopSm) return 'desktop-sm'
  if (tablet) return 'tablet'
  return 'mobile'
}

function getInitial(): Breakpoint {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return 'desktop'
  return resolve(
    window.matchMedia(QUERY_DESKTOP).matches,
    window.matchMedia(QUERY_DESKTOP_SM).matches,
    window.matchMedia(QUERY_TABLET).matches,
  )
}

/**
 * Reactive viewport breakpoint detection using matchMedia listeners.
 *
 * Returns the current breakpoint and boolean convenience flags.
 * Does not use resize events -- matchMedia change listeners are more efficient.
 */
export function useBreakpoint(): UseBreakpointReturn {
  const [breakpoint, setBreakpoint] = useState<Breakpoint>(getInitial)

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return

    const mqDesktop = window.matchMedia(QUERY_DESKTOP)
    const mqDesktopSm = window.matchMedia(QUERY_DESKTOP_SM)
    const mqTablet = window.matchMedia(QUERY_TABLET)

    function update() {
      setBreakpoint(resolve(mqDesktop.matches, mqDesktopSm.matches, mqTablet.matches))
    }

    mqDesktop.addEventListener('change', update)
    mqDesktopSm.addEventListener('change', update)
    mqTablet.addEventListener('change', update)

    return () => {
      mqDesktop.removeEventListener('change', update)
      mqDesktopSm.removeEventListener('change', update)
      mqTablet.removeEventListener('change', update)
    }
  }, [])

  return {
    breakpoint,
    isDesktop: breakpoint === 'desktop' || breakpoint === 'desktop-sm',
    isTablet: breakpoint === 'tablet',
    isMobile: breakpoint === 'mobile',
  }
}
