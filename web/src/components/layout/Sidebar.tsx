import { useState } from 'react'
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
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'
import { useCommandPalette } from '@/hooks/useCommandPalette'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
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

export function Sidebar() {
  const [localCollapsed, setLocalCollapsed] = useState(readCollapsed)
  const sidebarMode = useThemeStore((s) => s.sidebarMode)
  const { user } = useAuth()
  const logout = useAuthStore((s) => s.logout)
  const { open: openCommandPalette } = useCommandPalette()

  const shortcutKey = typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.platform) ? '⌘' : 'Ctrl'

  // Sidebar mode determines structure; local toggle only applies in collapsible mode
  const collapsed =
    sidebarMode === 'rail' || sidebarMode === 'compact'
      ? true
      : sidebarMode === 'persistent'
        ? false
        : localCollapsed

  const showCollapseToggle = sidebarMode === 'collapsible'

  function toggleCollapse() {
    setLocalCollapsed((prev) => {
      const next = !prev
      writeCollapsed(next)
      return next
    })
  }

  // Hidden mode: don't render the sidebar at all
  if (sidebarMode === 'hidden') return null

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

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-2 pt-3" aria-label="Main navigation">
        <div className="flex flex-col gap-1">
          <SidebarNavItem
            to={ROUTES.DASHBOARD}
            icon={LayoutDashboard}
            label="Dashboard"
            collapsed={collapsed}
            end
          />
          <SidebarNavItem
            to={ROUTES.ORG}
            icon={GitBranch}
            label="Org Chart"
            collapsed={collapsed}
          />
          <SidebarNavItem
            to={ROUTES.TASKS}
            icon={KanbanSquare}
            label="Task Board"
            collapsed={collapsed}
          />
          <SidebarNavItem
            to={ROUTES.BUDGET}
            icon={DollarSign}
            label="Budget"
            collapsed={collapsed}
          />
          <SidebarNavItem
            to={ROUTES.APPROVALS}
            icon={ShieldCheck}
            label="Approvals"
            collapsed={collapsed}
            badge={0}
          />
        </div>

        {/* Workspace section */}
        <div className="mt-4 border-t border-border pt-3">
          {!collapsed && (
            <span className="mb-2 block px-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Workspace
            </span>
          )}
          <div className="flex flex-col gap-1">
            <SidebarNavItem
              to={ROUTES.AGENTS}
              icon={Users}
              label="Agents"
              collapsed={collapsed}
            />
            <SidebarNavItem
              to={ROUTES.MESSAGES}
              icon={MessageSquare}
              label="Messages"
              collapsed={collapsed}
              badge={0}
            />
            <SidebarNavItem
              to={ROUTES.MEETINGS}
              icon={Video}
              label="Meetings"
              collapsed={collapsed}
            />
            <SidebarNavItem
              to={ROUTES.PROVIDERS}
              icon={Cpu}
              label="Providers"
              collapsed={collapsed}
            />
            <SidebarNavItem
              to={ROUTES.SETTINGS}
              icon={Settings}
              label="Settings"
              collapsed={collapsed}
            />
          </div>
        </div>
      </nav>

      {/* Bottom section (non-navigation controls) */}
      <div className="border-t border-border px-2 py-3">
        <div className="flex flex-col gap-1">
          {/* Collapse toggle (only in collapsible mode) */}
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

          {/* Notifications placeholder */}
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

          {/* Cmd+K / Ctrl+K search trigger */}
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

          {/* Connection status placeholder */}
          <div
            className={cn(
              'flex items-center gap-3 px-3 py-1',
              collapsed && 'justify-center',
            )}
          >
            <span
              className="size-2 rounded-full bg-success"
              title="Connected"
              aria-label="Connection status: connected"
            />
            {!collapsed && (
              <span className="text-xs text-muted-foreground">Connected</span>
            )}
          </div>

          {/* User / logout */}
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
    </aside>
  )
}
