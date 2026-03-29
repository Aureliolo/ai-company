import { useEffect, useState } from 'react'
import { useLocation } from 'react-router'
import { FocusScope } from '@radix-ui/react-focus-scope'
import {
  Bell,
  Command,
  Cpu,
  DollarSign,
  GitBranch,
  KanbanSquare,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  ShieldCheck,
  Users,
  Video,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'
import { useBreakpoint } from '@/hooks/useBreakpoint'
import { useCommandPalette } from '@/hooks/useCommandPalette'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useWebSocketStore } from '@/stores/websocket'
import { ROUTES } from '@/router/routes'
import { SidebarNavItem } from './SidebarNavItem'

export const STORAGE_KEY = 'sidebar_collapsed'

const SIDEBAR_BUTTON_CLASS = cn(
  'flex items-center gap-3 rounded-md px-3 py-2 text-sm',
  'text-text-secondary transition-colors',
  'hover:bg-card-hover hover:text-foreground',
)

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'true'
  } catch {
    return false
  }
}

function writeCollapsed(value: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, String(value))
  } catch {
    // Ignore -- storage may be unavailable (e.g. quota exceeded)
  }
}

interface SidebarProps {
  /** Whether the overlay sidebar is open (tablet mode). Controlled by parent. */
  overlayOpen?: boolean
  /** Callback to close the overlay sidebar. */
  onOverlayClose?: () => void
}

export function Sidebar({ overlayOpen = false, onOverlayClose }: SidebarProps) {
  const [localCollapsed, setLocalCollapsed] = useState(readCollapsed)
  const sidebarMode = useThemeStore((s) => s.sidebarMode)
  const { user } = useAuth()
  const logout = useAuthStore((s) => s.logout)
  const { open: openCommandPalette } = useCommandPalette()
  const wsConnected = useWebSocketStore((s) => s.connected)
  const wsReconnectExhausted = useWebSocketStore((s) => s.reconnectExhausted)
  const { breakpoint } = useBreakpoint()
  const location = useLocation()

  const shortcutKey = typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.platform) ? '⌘' : 'Ctrl'

  // Close overlay on navigation
  useEffect(() => {
    if (overlayOpen && onOverlayClose) {
      onOverlayClose()
    }
    // Only trigger on route changes, not on prop changes
    // eslint-disable-next-line @eslint-react/exhaustive-deps
  }, [location.pathname])

  // Compute effective sidebar state based on breakpoint
  // Do NOT mutate the theme store -- keep user preference intact
  const isOverlayMode = breakpoint === 'tablet'
  const isHidden = breakpoint === 'mobile'

  // At desktop-sm, force collapsed regardless of user preference
  const effectiveCollapsed =
    breakpoint === 'desktop-sm'
      ? true
      : sidebarMode === 'rail' || sidebarMode === 'compact'
        ? true
        : sidebarMode === 'persistent'
          ? false
          : localCollapsed

  const collapsed = isOverlayMode ? false : effectiveCollapsed
  const showCollapseToggle = breakpoint === 'desktop' && sidebarMode === 'collapsible'

  function toggleCollapse() {
    setLocalCollapsed((prev) => {
      const next = !prev
      writeCollapsed(next)
      return next
    })
  }

  // Hidden at mobile or when sidebarMode is 'hidden' at desktop
  if (isHidden) return null
  if (breakpoint === 'desktop' && sidebarMode === 'hidden') return null

  // At tablet, render as overlay with backdrop
  if (isOverlayMode) {
    if (!overlayOpen) return null

    return (
      <>
        {/* Backdrop */}
        <div
          className="fixed inset-0 z-40 bg-black/50"
          onClick={onOverlayClose}
          aria-hidden="true"
        />
        {/* Overlay sidebar */}
        <aside
          className="fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-border bg-surface"
          role="dialog"
          aria-label="Navigation menu"
          onKeyDown={(e) => { if (e.key === 'Escape') onOverlayClose?.() }}
        >
          <FocusScope trapped loop>
            <div className="flex h-14 shrink-0 items-center justify-between border-b border-border px-3">
              <span className="text-lg font-bold text-accent">SynthOrg</span>
              <button
                onClick={onOverlayClose}
                aria-label="Close navigation menu"
                className="rounded-md p-1 text-muted-foreground hover:bg-card-hover hover:text-foreground"
              >
                <X className="size-5" aria-hidden="true" />
              </button>
            </div>
            <SidebarNav collapsed={false} />
            <SidebarFooter
              collapsed={false}
              showCollapseToggle={false}
              toggleCollapse={toggleCollapse}
              openCommandPalette={openCommandPalette}
              shortcutKey={shortcutKey}
              wsConnected={wsConnected}
              wsReconnectExhausted={wsReconnectExhausted}
              user={user}
              logout={logout}
            />
          </FocusScope>
        </aside>
      </>
    )
  }

  // Normal desktop sidebar
  return (
    <aside
      className={cn(
        'flex h-full flex-col border-r border-border bg-surface transition-[width] duration-200',
        sidebarMode === 'compact' ? 'w-[var(--so-sidebar-compact)]' : collapsed ? 'w-[var(--so-sidebar-collapsed)]' : 'w-[var(--so-sidebar-expanded)]',
      )}
    >
      {/* Header */}
      <div className="flex h-14 shrink-0 items-center border-b border-border px-3">
        {collapsed ? (
          <span className="mx-auto text-lg font-bold text-accent">S</span>
        ) : (
          <span className="text-lg font-bold text-accent">SynthOrg</span>
        )}
      </div>

      <SidebarNav collapsed={collapsed} />
      <SidebarFooter
        collapsed={collapsed}
        showCollapseToggle={showCollapseToggle}
        toggleCollapse={toggleCollapse}
        openCommandPalette={openCommandPalette}
        shortcutKey={shortcutKey}
        wsConnected={wsConnected}
        wsReconnectExhausted={wsReconnectExhausted}
        user={user}
        logout={logout}
      />
    </aside>
  )
}

// ── Extracted sub-components to share between normal and overlay modes ──

function SidebarNav({ collapsed }: { collapsed: boolean }) {
  return (
    <nav className="flex-1 overflow-y-auto px-2 pt-3" aria-label="Main navigation">
      <div className="flex flex-col gap-1">
        <SidebarNavItem to={ROUTES.DASHBOARD} icon={LayoutDashboard} label="Dashboard" collapsed={collapsed} end />
        <SidebarNavItem to={ROUTES.ORG} icon={GitBranch} label="Org Chart" collapsed={collapsed} />
        <SidebarNavItem to={ROUTES.TASKS} icon={KanbanSquare} label="Task Board" collapsed={collapsed} />
        <SidebarNavItem to={ROUTES.BUDGET} icon={DollarSign} label="Budget" collapsed={collapsed} />
        <SidebarNavItem to={ROUTES.APPROVALS} icon={ShieldCheck} label="Approvals" collapsed={collapsed} badge={0} />
      </div>

      <div className="mt-4 border-t border-border pt-3">
        {!collapsed && (
          <span className="mb-2 block px-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Workspace
          </span>
        )}
        <div className="flex flex-col gap-1">
          <SidebarNavItem to={ROUTES.AGENTS} icon={Users} label="Agents" collapsed={collapsed} />
          <SidebarNavItem to={ROUTES.MESSAGES} icon={MessageSquare} label="Messages" collapsed={collapsed} badge={0} />
          <SidebarNavItem to={ROUTES.MEETINGS} icon={Video} label="Meetings" collapsed={collapsed} />
          <SidebarNavItem to={ROUTES.PROVIDERS} icon={Cpu} label="Providers" collapsed={collapsed} />
          <SidebarNavItem to={ROUTES.SETTINGS} icon={Settings} label="Settings" collapsed={collapsed} />
        </div>
      </div>
    </nav>
  )
}

interface SidebarFooterProps {
  collapsed: boolean
  showCollapseToggle: boolean
  toggleCollapse: () => void
  openCommandPalette: () => void
  shortcutKey: string
  wsConnected: boolean
  wsReconnectExhausted: boolean
  user: { username: string; role: string } | null
  logout: () => void
}

function SidebarFooter({
  collapsed,
  showCollapseToggle,
  toggleCollapse,
  openCommandPalette,
  shortcutKey,
  wsConnected,
  wsReconnectExhausted,
  user,
  logout,
}: SidebarFooterProps) {
  return (
    <div className="border-t border-border px-2 py-3">
      <div className="flex flex-col gap-1">
        {showCollapseToggle && (
          <button
            onClick={toggleCollapse}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className={SIDEBAR_BUTTON_CLASS}
          >
            {collapsed ? (
              <PanelLeftOpen className="mx-auto size-5" aria-hidden="true" />
            ) : (
              <>
                <PanelLeftClose className="size-5 shrink-0" aria-hidden="true" />
                <span>Collapse</span>
              </>
            )}
          </button>
        )}

        <button
          title="Notifications"
          aria-label="Notifications"
          className={SIDEBAR_BUTTON_CLASS}
        >
          <Bell
            className={cn('size-5 shrink-0', collapsed && 'mx-auto')}
            aria-hidden="true"
          />
          {!collapsed && <span>Notifications</span>}
        </button>

        <button
          onClick={openCommandPalette}
          title={`Search (${shortcutKey}+K)`}
          aria-label="Search commands"
          className={SIDEBAR_BUTTON_CLASS}
        >
          <Command
            className={cn('size-4 shrink-0', collapsed && 'mx-auto')}
            aria-hidden="true"
          />
          {!collapsed && (
            <span className="text-xs">
              {shortcutKey}+K to search
            </span>
          )}
        </button>

        {/* WebSocket connection status */}
        <div
          className={cn(
            'flex items-center gap-3 px-3 py-1',
            collapsed && 'justify-center',
          )}
        >
          <span
            className={cn(
              'size-2 shrink-0 rounded-full',
              wsConnected
                ? 'bg-success'
                : wsReconnectExhausted
                  ? 'bg-danger'
                  : 'bg-warning animate-pulse',
            )}
            title={
              wsConnected
                ? 'Connected'
                : wsReconnectExhausted
                  ? 'Disconnected'
                  : 'Reconnecting...'
            }
            aria-label={
              wsConnected
                ? 'Connection status: connected'
                : wsReconnectExhausted
                  ? 'Connection status: disconnected'
                  : 'Connection status: reconnecting'
            }
          />
          {!collapsed && (
            <span className="text-xs text-muted-foreground">
              {wsConnected
                ? 'Connected'
                : wsReconnectExhausted
                  ? 'Disconnected'
                  : 'Reconnecting...'}
            </span>
          )}
        </div>

        {user && (
          <div
            className={cn(
              'flex items-center gap-3 px-3 py-2',
              collapsed && 'justify-center',
            )}
          >
            {!collapsed && (
              <div className="flex-1 truncate">
                <div className="text-sm font-medium text-foreground">
                  {user.username}
                </div>
                <div className="text-xs text-muted-foreground">{user.role}</div>
              </div>
            )}
            <button
              onClick={logout}
              title="Logout"
              aria-label="Logout"
              className={cn(
                'rounded-md p-1 text-muted-foreground',
                'transition-colors',
                'hover:bg-card-hover hover:text-foreground',
              )}
            >
              <LogOut className="size-4" aria-hidden="true" />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
