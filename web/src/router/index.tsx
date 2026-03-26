import { lazy, Suspense } from 'react'
import { createBrowserRouter, RouterProvider } from 'react-router'
import { AuthGuard, GuestGuard, SetupCompleteGuard, SetupGuard } from './guards'

// Lazy-loaded pages
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const LoginPage = lazy(() => import('@/pages/LoginPage'))
const SetupPage = lazy(() => import('@/pages/SetupPage'))
const OrgChartPage = lazy(() => import('@/pages/OrgChartPage'))
const OrgEditPage = lazy(() => import('@/pages/OrgEditPage'))
const TaskBoardPage = lazy(() => import('@/pages/TaskBoardPage'))
const TaskDetailPage = lazy(() => import('@/pages/TaskDetailPage'))
const BudgetPage = lazy(() => import('@/pages/BudgetPage'))
const BudgetForecastPage = lazy(() => import('@/pages/BudgetForecastPage'))
const ApprovalsPage = lazy(() => import('@/pages/ApprovalsPage'))
const AgentsPage = lazy(() => import('@/pages/AgentsPage'))
const AgentDetailPage = lazy(() => import('@/pages/AgentDetailPage'))
const MessagesPage = lazy(() => import('@/pages/MessagesPage'))
const MeetingsPage = lazy(() => import('@/pages/MeetingsPage'))
const MeetingDetailPage = lazy(() => import('@/pages/MeetingDetailPage'))
const ProvidersPage = lazy(() => import('@/pages/ProvidersPage'))
const ProviderDetailPage = lazy(() => import('@/pages/ProviderDetailPage'))
const SettingsPage = lazy(() => import('@/pages/SettingsPage'))
const SettingsNamespacePage = lazy(() => import('@/pages/SettingsNamespacePage'))
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'))
const AppLayout = lazy(() => import('@/components/layout/AppLayout'))

function SuspenseWrapper({ children }: { children: React.ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center">
          <span className="text-sm text-muted-foreground">Loading...</span>
        </div>
      }
    >
      {children}
    </Suspense>
  )
}

const router = createBrowserRouter([
  // Public: Login
  {
    path: '/login',
    element: (
      <GuestGuard>
        <SuspenseWrapper>
          <LoginPage />
        </SuspenseWrapper>
      </GuestGuard>
    ),
  },
  // Public: Setup wizard
  {
    path: '/setup',
    element: (
      <SetupCompleteGuard>
        <SuspenseWrapper>
          <SetupPage />
        </SuspenseWrapper>
      </SetupCompleteGuard>
    ),
  },
  {
    path: '/setup/:step',
    element: (
      <SetupCompleteGuard>
        <SuspenseWrapper>
          <SetupPage />
        </SuspenseWrapper>
      </SetupCompleteGuard>
    ),
  },
  // Protected: All app routes with layout shell
  {
    element: <AuthGuard />,
    children: [
      {
        element: <SetupGuard />,
        children: [
          {
            element: (
              <SuspenseWrapper>
                <AppLayout />
              </SuspenseWrapper>
            ),
            children: [
              { index: true, element: <DashboardPage /> },
              { path: 'org', element: <OrgChartPage /> },
              { path: 'org/edit', element: <OrgEditPage /> },
              { path: 'tasks', element: <TaskBoardPage /> },
              { path: 'tasks/:taskId', element: <TaskDetailPage /> },
              { path: 'budget', element: <BudgetPage /> },
              { path: 'budget/forecast', element: <BudgetForecastPage /> },
              { path: 'approvals', element: <ApprovalsPage /> },
              { path: 'agents', element: <AgentsPage /> },
              { path: 'agents/:agentName', element: <AgentDetailPage /> },
              { path: 'messages', element: <MessagesPage /> },
              { path: 'meetings', element: <MeetingsPage /> },
              { path: 'meetings/:meetingId', element: <MeetingDetailPage /> },
              { path: 'providers', element: <ProvidersPage /> },
              { path: 'providers/:providerName', element: <ProviderDetailPage /> },
              { path: 'settings', element: <SettingsPage /> },
              { path: 'settings/:namespace', element: <SettingsNamespacePage /> },
              { path: '*', element: <NotFoundPage /> },
            ],
          },
        ],
      },
    ],
  },
])

export function AppRouter() {
  return <RouterProvider router={router} />
}
