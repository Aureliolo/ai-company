import { Suspense, useMemo } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router'
import {
  Cpu,
  DollarSign,
  KanbanSquare,
  LayoutDashboard,
  MessageSquare,
  Palette,
  Settings,
  ShieldCheck,
  Users,
  Video,
  GitBranch,
} from 'lucide-react'
import { ROUTES } from '@/router/routes'
import type { CommandItem } from '@/hooks/useCommandPalette'
import { useRegisterCommands } from '@/hooks/useCommandPalette'
import { useThemeStore } from '@/stores/theme'
import { AnimatedPresence } from '@/components/ui/animated-presence'
import { CommandPalette } from '@/components/ui/command-palette'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { SkeletonCard } from '@/components/ui/skeleton'
import { ToastContainer } from '@/components/ui/toast'
import { Sidebar } from './Sidebar'
import { StatusBar } from './StatusBar'

function PageLoadingFallback() {
  return (
    <div className="space-y-4 p-2" role="status" aria-live="polite">
      <SkeletonCard header lines={2} />
      <div className="grid grid-cols-4 gap-4">
        <SkeletonCard lines={1} />
        <SkeletonCard lines={1} />
        <SkeletonCard lines={1} />
        <SkeletonCard lines={1} />
      </div>
    </div>
  )
}

export default function AppLayout() {
  const location = useLocation()
  const navigate = useNavigate()

  // Register global navigation commands for the command palette
  const globalCommands: CommandItem[] = useMemo(
    () => [
      { id: 'nav-dashboard', label: 'Dashboard', icon: LayoutDashboard, action: () => navigate(ROUTES.DASHBOARD), group: 'Navigation' },
      { id: 'nav-org', label: 'Org Chart', icon: GitBranch, action: () => navigate(ROUTES.ORG), group: 'Navigation' },
      { id: 'nav-tasks', label: 'Tasks', icon: KanbanSquare, action: () => navigate(ROUTES.TASKS), group: 'Navigation' },
      { id: 'nav-budget', label: 'Budget', icon: DollarSign, action: () => navigate(ROUTES.BUDGET), group: 'Navigation' },
      { id: 'nav-approvals', label: 'Approvals', icon: ShieldCheck, action: () => navigate(ROUTES.APPROVALS), group: 'Navigation' },
      { id: 'nav-agents', label: 'Agents', icon: Users, action: () => navigate(ROUTES.AGENTS), group: 'Navigation' },
      { id: 'nav-messages', label: 'Messages', icon: MessageSquare, action: () => navigate(ROUTES.MESSAGES), group: 'Navigation' },
      { id: 'nav-meetings', label: 'Meetings', icon: Video, action: () => navigate(ROUTES.MEETINGS), group: 'Navigation' },
      { id: 'nav-providers', label: 'Providers', icon: Cpu, action: () => navigate(ROUTES.PROVIDERS), group: 'Navigation' },
      { id: 'nav-settings', label: 'Settings', icon: Settings, action: () => navigate(ROUTES.SETTINGS), group: 'Navigation', shortcut: ['ctrl', ','] },
    ],
    [navigate],
  )
  useRegisterCommands(globalCommands)

  const themeCommands: CommandItem[] = useMemo(
    () => [
      { id: 'theme-open', label: 'Open theme preferences', icon: Palette, action: () => useThemeStore.getState().setPopoverOpen(true), group: 'Theme', keywords: ['theme', 'appearance', 'customize'] },
      { id: 'theme-warm-ops', label: 'Theme: Warm Ops', action: () => useThemeStore.getState().setColorPalette('warm-ops'), group: 'Theme', keywords: ['color', 'palette', 'blue'] },
      { id: 'theme-ice-station', label: 'Theme: Ice Station', action: () => useThemeStore.getState().setColorPalette('ice-station'), group: 'Theme', keywords: ['color', 'palette', 'green', 'mint'] },
      { id: 'theme-stealth', label: 'Theme: Stealth', action: () => useThemeStore.getState().setColorPalette('stealth'), group: 'Theme', keywords: ['color', 'palette', 'purple', 'violet'] },
      { id: 'theme-signal', label: 'Theme: Signal', action: () => useThemeStore.getState().setColorPalette('signal'), group: 'Theme', keywords: ['color', 'palette', 'orange', 'amber'] },
      { id: 'theme-neon', label: 'Theme: Neon', action: () => useThemeStore.getState().setColorPalette('neon'), group: 'Theme', keywords: ['color', 'palette', 'cyan'] },
      { id: 'density-dense', label: 'Set density: Dense', action: () => useThemeStore.getState().setDensity('dense'), group: 'Theme', keywords: ['compact', 'tight', 'density'] },
      { id: 'density-balanced', label: 'Set density: Balanced', action: () => useThemeStore.getState().setDensity('balanced'), group: 'Theme', keywords: ['default', 'density'] },
      { id: 'density-medium', label: 'Set density: Medium', action: () => useThemeStore.getState().setDensity('medium'), group: 'Theme', keywords: ['density'] },
      { id: 'density-sparse', label: 'Set density: Sparse', action: () => useThemeStore.getState().setDensity('sparse'), group: 'Theme', keywords: ['spacious', 'density'] },
      { id: 'font-geist', label: 'Font: Geist', action: () => useThemeStore.getState().setTypography('geist'), group: 'Theme', keywords: ['typography', 'font'] },
      { id: 'font-jetbrains', label: 'Font: JetBrains + Inter', action: () => useThemeStore.getState().setTypography('jetbrains'), group: 'Theme', keywords: ['typography', 'font'] },
      { id: 'font-ibm-plex', label: 'Font: IBM Plex', action: () => useThemeStore.getState().setTypography('ibm-plex'), group: 'Theme', keywords: ['typography', 'font'] },
      { id: 'animation-minimal', label: 'Motion: Minimal', action: () => useThemeStore.getState().setAnimation('minimal'), group: 'Theme', keywords: ['animation', 'reduced'] },
      { id: 'animation-spring', label: 'Motion: Spring', action: () => useThemeStore.getState().setAnimation('spring'), group: 'Theme', keywords: ['animation', 'bouncy'] },
      { id: 'animation-instant', label: 'Motion: Instant', action: () => useThemeStore.getState().setAnimation('instant'), group: 'Theme', keywords: ['animation', 'none'] },
      { id: 'animation-status', label: 'Motion: Status-driven', action: () => useThemeStore.getState().setAnimation('status-driven'), group: 'Theme', keywords: ['animation'] },
      { id: 'animation-aggressive', label: 'Motion: Aggressive', action: () => useThemeStore.getState().setAnimation('aggressive'), group: 'Theme', keywords: ['animation', 'energy'] },
      { id: 'sidebar-rail', label: 'Sidebar: Rail', action: () => useThemeStore.getState().setSidebarMode('rail'), group: 'Theme', keywords: ['sidebar', 'icons'] },
      { id: 'sidebar-collapsible', label: 'Sidebar: Collapsible', action: () => useThemeStore.getState().setSidebarMode('collapsible'), group: 'Theme', keywords: ['sidebar', 'default'] },
      { id: 'sidebar-hidden', label: 'Sidebar: Hidden', action: () => useThemeStore.getState().setSidebarMode('hidden'), group: 'Theme', keywords: ['sidebar', 'full'] },
      { id: 'sidebar-persistent', label: 'Sidebar: Persistent', action: () => useThemeStore.getState().setSidebarMode('persistent'), group: 'Theme', keywords: ['sidebar', 'always'] },
      { id: 'sidebar-compact', label: 'Sidebar: Compact', action: () => useThemeStore.getState().setSidebarMode('compact'), group: 'Theme', keywords: ['sidebar', 'narrow'] },
    ],
    [],
  )
  useRegisterCommands(themeCommands)

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      <StatusBar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-6">
          <ErrorBoundary level="page" onReset={() => navigate(ROUTES.DASHBOARD)}>
            <Suspense fallback={<PageLoadingFallback />}>
              <AnimatedPresence routeKey={location.pathname}>
                <Outlet />
              </AnimatedPresence>
            </Suspense>
          </ErrorBoundary>
        </main>
      </div>
      <ToastContainer />
      <CommandPalette />
    </div>
  )
}
