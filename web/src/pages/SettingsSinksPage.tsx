import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { Activity, ArrowLeft } from 'lucide-react'
import type { SinkInfo } from '@/api/types'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { useSinksStore } from '@/stores/sinks'
import { SinkCard } from './settings/sinks/SinkCard'
import { SinkFormDrawer } from './settings/sinks/SinkFormDrawer'

export default function SettingsSinksPage() {
  const navigate = useNavigate()
  const { sinks, loading, error, fetchSinks, testConfig } = useSinksStore()
  const [editSink, setEditSink] = useState<SinkInfo | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  useEffect(() => {
    fetchSinks()
  }, [fetchSinks])

  const handleEdit = useCallback((sink: SinkInfo) => {
    setEditSink(sink)
    setDrawerOpen(true)
  }, [])

  const handleCloseDrawer = useCallback(() => {
    setDrawerOpen(false)
    setEditSink(null)
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate('/settings')}>
          <ArrowLeft className="mr-1.5 size-3.5" aria-hidden />
          Settings
        </Button>
        <div className="flex items-center gap-2">
          <Activity className="size-4 text-text-secondary" aria-hidden />
          <h1 className="text-lg font-semibold text-foreground">Log Sinks</h1>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-danger/30 bg-danger/5 px-4 py-2 text-sm text-danger">
          {error}
        </div>
      )}

      {!loading && sinks.length === 0 && (
        <EmptyState
          icon={Activity}
          title="No sinks configured"
          description="Log sinks will appear once the observability system is initialized."
        />
      )}

      <ErrorBoundary level="section">
        <StaggerGroup className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sinks.map((sink) => (
            <StaggerItem key={sink.identifier}>
              <SinkCard sink={sink} onEdit={handleEdit} />
            </StaggerItem>
          ))}
        </StaggerGroup>
      </ErrorBoundary>

      <SinkFormDrawer
        open={drawerOpen}
        onClose={handleCloseDrawer}
        sink={editSink}
        onTest={testConfig}
      />
    </div>
  )
}
