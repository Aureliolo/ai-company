import { Suspense, useMemo } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router'
import {
  Cpu,
  DollarSign,
  KanbanSquare,
  LayoutDashboard,
  MessageSquare,
  Settings,
  ShieldCheck,
  Users,
  Video,
  GitBranch,
} from 'lucide-react'
import { ROUTES } from '@/router/routes'
import type { CommandItem } from '@/hooks/useCommandPalette'
import { useRegisterCommands } from '@/hooks/useCommandPalette'
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
