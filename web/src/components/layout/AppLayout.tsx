import { Suspense } from 'react'
import { Outlet } from 'react-router'
import { Sidebar } from './Sidebar'
import { StatusBar } from './StatusBar'

function PageLoadingFallback() {
  return (
    <div className="flex h-full items-center justify-center" role="status" aria-live="polite">
      <span className="text-sm text-muted-foreground">Loading...</span>
    </div>
  )
}

export default function AppLayout() {
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      <StatusBar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-6">
          <Suspense fallback={<PageLoadingFallback />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  )
}
