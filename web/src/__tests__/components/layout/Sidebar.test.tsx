import { act, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import fc from 'fast-check'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { Sidebar } from '@/components/layout/Sidebar'
import { ROUTES } from '@/router/routes'
import { renderWithRouter } from '../../test-utils'

// Mock components defined at module level for ESLint compliance
function MockAnimatePresence({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

// React 19: ref is a regular prop, no forwardRef needed
function MockMotionDiv({ children, ref, ...allProps }: React.ComponentProps<'div'> & { ref?: React.Ref<HTMLDivElement> } & Record<string, unknown>) {
  const domProps = Object.fromEntries(
    Object.entries(allProps).filter(([key]) => !['variants', 'initial', 'animate', 'exit', 'transition'].includes(key)),
  ) as React.HTMLAttributes<HTMLDivElement>
  return <div ref={ref} {...domProps}>{children as React.ReactNode}</div>
}

vi.mock('motion/react', async () => {
  const actual = await vi.importActual<typeof import('motion/react')>('motion/react')
  return {
    ...actual,
    AnimatePresence: MockAnimatePresence,
    motion: new Proxy(actual.motion as object, {
      get(target, prop, receiver) {
        if (prop === 'div') return MockMotionDiv
        return Reflect.get(target, prop, receiver)
      },
    }) as typeof actual.motion,
  }
})

// Mock useBreakpoint so we can control breakpoint per-test
const getBreakpoint = vi.fn()
vi.mock('@/hooks/useBreakpoint', () => ({

  useBreakpoint: () => getBreakpoint(),
}))

// Prevent window.location side effects from auth store
const originalLocation = window.location
beforeAll(() => {
  Object.defineProperty(window, 'location', {
    writable: true,
    value: { ...originalLocation, href: '', pathname: '/' },
  })
})
afterAll(() => {
  Object.defineProperty(window, 'location', {
    writable: true,
    value: originalLocation,
  })
})

function resetStore() {
  useAuthStore.setState({
    authStatus: 'unauthenticated' as const,
    user: null,
    loading: false,
  })
}

function setup(initialEntries: string[] = ['/']) {
  useAuthStore.setState({
    authStatus: 'authenticated' as const,
    user: { id: '1', username: 'admin', role: 'ceo', must_change_password: false, org_roles: [], scoped_departments: [] },
    loading: false,
  })
  return renderWithRouter(<Sidebar />, { initialEntries })
}

describe('Sidebar', () => {
  beforeEach(() => {
    resetStore()
    useThemeStore.getState().setSidebarMode('collapsible')
    localStorage.clear()
    vi.clearAllMocks()
    getBreakpoint.mockReturnValue({
      breakpoint: 'desktop',
      isDesktop: true,
      isTablet: false,
      isMobile: false,
    })
  })

  it('renders all primary navigation items', () => {
    setup()

    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.getByText('Org Chart')).toBeInTheDocument()
    expect(screen.getByText('Task Board')).toBeInTheDocument()
    expect(screen.getByText('Budget')).toBeInTheDocument()
    expect(screen.getByText('Approvals')).toBeInTheDocument()
  })

  it('renders all workspace navigation items', () => {
    setup()

    expect(screen.getByText('Agents')).toBeInTheDocument()
    expect(screen.getByText('Messages')).toBeInTheDocument()
    expect(screen.getByText('Meetings')).toBeInTheDocument()
    expect(screen.getByText('Providers')).toBeInTheDocument()
    expect(screen.getByText('Docs')).toBeInTheDocument()
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })

  it('renders the Workspace section label', () => {
    setup()

    expect(screen.getByText('Workspace')).toBeInTheDocument()
  })

  it('renders user info when authenticated', () => {
    setup()

    expect(screen.getByText('admin')).toBeInTheDocument()
    expect(screen.getByText('ceo')).toBeInTheDocument()
  })

  it('collapses and persists state to localStorage', async () => {
    const user = userEvent.setup()
    setup()

    expect(screen.getByText('SynthOrg')).toBeInTheDocument()
    expect(localStorage.getItem('sidebar_collapsed')).toBeNull()

    await user.click(screen.getByTitle('Collapse sidebar'))

    expect(screen.queryByText('SynthOrg')).not.toBeInTheDocument()
    expect(localStorage.getItem('sidebar_collapsed')).toBe('true')
  })

  it('expands from collapsed state', async () => {
    localStorage.setItem('sidebar_collapsed', 'true')
    const user = userEvent.setup()
    setup()

    expect(screen.queryByText('SynthOrg')).not.toBeInTheDocument()

    await user.click(screen.getByTitle('Expand sidebar'))

    expect(screen.getByText('SynthOrg')).toBeInTheDocument()
    expect(localStorage.getItem('sidebar_collapsed')).toBe('false')
  })

  it('hides Workspace label when collapsed', () => {
    localStorage.setItem('sidebar_collapsed', 'true')
    setup()

    expect(screen.queryByText('Workspace')).not.toBeInTheDocument()
  })

  it('renders brand mark when collapsed', () => {
    localStorage.setItem('sidebar_collapsed', 'true')
    setup()

    expect(screen.getByText('S')).toBeInTheDocument()
  })

  it('calls logout when logout button is clicked', async () => {
    const user = userEvent.setup()
    const logoutSpy = vi.fn()
    useAuthStore.setState({
      ...useAuthStore.getState(),
      authStatus: 'authenticated',
      user: { id: '1', username: 'admin', role: 'ceo', must_change_password: false, org_roles: [], scoped_departments: [] },
      loading: false,
        logout: logoutSpy,
    })
    renderWithRouter(<Sidebar />, { initialEntries: ['/'] })

    await user.click(screen.getByTitle('Logout'))

    expect(logoutSpy).toHaveBeenCalledOnce()
  })

  describe('sidebarMode', () => {
    it('returns null when mode is hidden', () => {
      useThemeStore.getState().setSidebarMode('hidden')
      setup()

      expect(screen.queryByLabelText('Main navigation')).not.toBeInTheDocument()
    })

    it('is always collapsed in rail mode (no collapse toggle)', () => {
      useThemeStore.getState().setSidebarMode('rail')
      setup()

      // Collapsed state shows brand mark "S" instead of "SynthOrg"
      expect(screen.getByText('S')).toBeInTheDocument()
      expect(screen.queryByText('SynthOrg')).not.toBeInTheDocument()

      // Collapse toggle should not be present
      expect(screen.queryByTitle('Collapse sidebar')).not.toBeInTheDocument()
      expect(screen.queryByTitle('Expand sidebar')).not.toBeInTheDocument()
    })

    it('is always collapsed in compact mode (no collapse toggle)', () => {
      useThemeStore.getState().setSidebarMode('compact')
      setup()

      expect(screen.getByText('S')).toBeInTheDocument()
      expect(screen.queryByText('SynthOrg')).not.toBeInTheDocument()

      expect(screen.queryByTitle('Collapse sidebar')).not.toBeInTheDocument()
      expect(screen.queryByTitle('Expand sidebar')).not.toBeInTheDocument()
    })

    it('is always expanded in persistent mode (no collapse toggle)', () => {
      useThemeStore.getState().setSidebarMode('persistent')
      setup()

      expect(screen.getByText('SynthOrg')).toBeInTheDocument()
      expect(screen.queryByText('S')).not.toBeInTheDocument()

      expect(screen.queryByTitle('Collapse sidebar')).not.toBeInTheDocument()
      expect(screen.queryByTitle('Expand sidebar')).not.toBeInTheDocument()
    })

    it('shows collapse toggle only in collapsible mode', () => {
      useThemeStore.getState().setSidebarMode('collapsible')
      setup()

      expect(screen.getByTitle('Collapse sidebar')).toBeInTheDocument()
    })
  })

  it('returns null at mobile breakpoint', () => {
    getBreakpoint.mockReturnValue({
      breakpoint: 'mobile',
      isDesktop: false,
      isTablet: false,
      isMobile: true,
    })
    setup()
    expect(screen.queryByLabelText('Main navigation')).not.toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('forces collapsed at desktop-sm breakpoint regardless of user preference', () => {
    getBreakpoint.mockReturnValue({
      breakpoint: 'desktop-sm',
      isDesktop: true,
      isTablet: false,
      isMobile: false,
    })
    localStorage.setItem('sidebar_collapsed', 'false')
    setup()
    // Collapsed shows brand mark "S" instead of "SynthOrg"
    expect(screen.getByText('S')).toBeInTheDocument()
    expect(screen.queryByText('SynthOrg')).not.toBeInTheDocument()
  })

  describe('tablet overlay', () => {
    function setupTablet(overlayOpen: boolean, onOverlayClose = vi.fn()) {
      getBreakpoint.mockReturnValue({
        breakpoint: 'tablet',
        isDesktop: false,
        isTablet: true,
        isMobile: false,
      })
      useAuthStore.setState({
        authStatus: 'authenticated',
        user: { id: '1', username: 'admin', role: 'ceo', must_change_password: false, org_roles: [], scoped_departments: [] },
        loading: false,
          })
      return {
        onOverlayClose,
        ...renderWithRouter(
          <Sidebar overlayOpen={overlayOpen} onOverlayClose={onOverlayClose} />,
          { initialEntries: ['/'] },
        ),
      }
    }

    it('renders nothing when overlayOpen is false', () => {
      setupTablet(false)
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('renders dialog when overlayOpen is true', () => {
      setupTablet(true)
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    it('has aria-label "Navigation menu"', () => {
      setupTablet(true)
      expect(screen.getByRole('dialog')).toHaveAttribute('aria-label', 'Navigation menu')
    })

    it('shows SynthOrg branding', () => {
      setupTablet(true)
      expect(screen.getByText('SynthOrg')).toBeInTheDocument()
    })

    it('renders navigation items', () => {
      setupTablet(true)
      expect(screen.getByText('Dashboard')).toBeInTheDocument()
      expect(screen.getByText('Settings')).toBeInTheDocument()
    })

    it('does not call onOverlayClose on mount', () => {
      const { onOverlayClose } = setupTablet(true)
      expect(onOverlayClose).not.toHaveBeenCalled()
    })

    it('calls onOverlayClose when close button is clicked', async () => {
      const user = userEvent.setup()
      const { onOverlayClose } = setupTablet(true)
      await user.click(screen.getByLabelText('Close navigation menu'))
      expect(onOverlayClose).toHaveBeenCalledOnce()
    })

    it('calls onOverlayClose when Escape is pressed', async () => {
      const user = userEvent.setup()
      const { onOverlayClose } = setupTablet(true)
      await user.keyboard('{Escape}')
      expect(onOverlayClose).toHaveBeenCalledOnce()
    })

    it('calls onOverlayClose when overlay backdrop is clicked', async () => {
      const user = userEvent.setup()
      const { onOverlayClose } = setupTablet(true)
      await user.click(screen.getByTestId('drawer-overlay'))
      expect(onOverlayClose).toHaveBeenCalledOnce()
    })

    it('calls onOverlayClose on route navigation', async () => {
      const onOverlayClose = vi.fn()
      const { router } = setupTablet(true, onOverlayClose)
      await act(() => router.navigate('/settings'))
      expect(onOverlayClose).toHaveBeenCalledOnce()
    })

    // Property: navigating to any different static route while overlay is open triggers exactly one close
    const staticRoutes = Object.values(ROUTES).filter((r) => !r.includes(':') && r !== '/')
    it('close-on-navigate fires exactly once for any static route (property)', { timeout: 15000 }, async () => {
      await fc.assert(
        fc.asyncProperty(fc.constantFrom(...staticRoutes), async (route) => {
          const onOverlayClose = vi.fn()
          const { router, unmount } = setupTablet(true, onOverlayClose)
          await act(() => router.navigate(route))
          expect(onOverlayClose).toHaveBeenCalledOnce()
          unmount()
        }),
      )
    })
  })
})
