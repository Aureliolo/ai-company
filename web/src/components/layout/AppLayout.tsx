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
import {
  useThemeStore,
  COLOR_PALETTES,
  DENSITIES,
  TYPOGRAPHIES,
  ANIMATION_PRESETS,
  SIDEBAR_MODES,
  type ColorPalette,
  type Density,
  type Typography,
  type AnimationPreset,
  type SidebarMode,
} from '@/stores/theme'
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

  const themeCommands: CommandItem[] = useMemo(() => {
    const PALETTE_META: Record<ColorPalette, { label: string; keywords: string[] }> = {
      'warm-ops': { label: 'Warm Ops', keywords: ['blue'] },
      'ice-station': { label: 'Ice Station', keywords: ['green', 'mint'] },
      stealth: { label: 'Stealth', keywords: ['purple', 'violet'] },
      signal: { label: 'Signal', keywords: ['orange', 'amber'] },
      neon: { label: 'Neon', keywords: ['cyan'] },
    }
    const DENSITY_META: Record<Density, { label: string; keywords: string[] }> = {
      dense: { label: 'Dense', keywords: ['compact', 'tight'] },
      balanced: { label: 'Balanced', keywords: ['default'] },
      medium: { label: 'Medium', keywords: [] },
      sparse: { label: 'Sparse', keywords: ['spacious'] },
    }
    const TYPOGRAPHY_META: Record<Typography, { label: string }> = {
      geist: { label: 'Geist' },
      jetbrains: { label: 'JetBrains + Inter' },
      'ibm-plex': { label: 'IBM Plex' },
    }
    const ANIMATION_META: Record<AnimationPreset, { label: string; keywords: string[] }> = {
      minimal: { label: 'Minimal', keywords: ['reduced'] },
      spring: { label: 'Spring', keywords: ['bouncy'] },
      instant: { label: 'Instant', keywords: ['none'] },
      'status-driven': { label: 'Status-driven', keywords: [] },
      aggressive: { label: 'Aggressive', keywords: ['energy'] },
    }
    const SIDEBAR_META: Record<SidebarMode, { label: string; keywords: string[] }> = {
      rail: { label: 'Rail', keywords: ['icons'] },
      collapsible: { label: 'Collapsible', keywords: ['default'] },
      hidden: { label: 'Hidden', keywords: ['full'] },
      persistent: { label: 'Persistent', keywords: ['always'] },
      compact: { label: 'Compact', keywords: ['narrow'] },
    }

    return [
      { id: 'theme-open', label: 'Open theme preferences', icon: Palette, action: () => useThemeStore.getState().setPopoverOpen(true), group: 'Theme', keywords: ['theme', 'appearance', 'customize'] },
      ...COLOR_PALETTES.map((v) => ({ id: `theme-${v}`, label: `Theme: ${PALETTE_META[v].label}`, action: () => useThemeStore.getState().setColorPalette(v), group: 'Theme', keywords: ['color', 'palette', ...PALETTE_META[v].keywords] })),
      ...DENSITIES.map((v) => ({ id: `density-${v}`, label: `Set density: ${DENSITY_META[v].label}`, action: () => useThemeStore.getState().setDensity(v), group: 'Theme', keywords: ['density', ...DENSITY_META[v].keywords] })),
      ...TYPOGRAPHIES.map((v) => ({ id: `font-${v}`, label: `Font: ${TYPOGRAPHY_META[v].label}`, action: () => useThemeStore.getState().setTypography(v), group: 'Theme', keywords: ['typography', 'font'] })),
      ...ANIMATION_PRESETS.map((v) => ({ id: `animation-${v}`, label: `Motion: ${ANIMATION_META[v].label}`, action: () => useThemeStore.getState().setAnimation(v), group: 'Theme', keywords: ['animation', ...ANIMATION_META[v].keywords] })),
      ...SIDEBAR_MODES.map((v) => ({ id: `sidebar-${v}`, label: `Sidebar: ${SIDEBAR_META[v].label}`, action: () => useThemeStore.getState().setSidebarMode(v), group: 'Theme', keywords: ['sidebar', ...SIDEBAR_META[v].keywords] })),
    ]
  }, [])
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
