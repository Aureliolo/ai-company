import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { Activity, ArrowLeft, Plus } from 'lucide-react'
import type { SinkInfo } from '@/api/types/settings'
import type { WsEvent } from '@/api/types/websocket'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { Skeleton } from '@/components/ui/skeleton'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useSinksStore } from '@/stores/sinks'
import { SinkCard } from './settings/sinks/SinkCard'
import { SinkFormDrawer } from './settings/sinks/SinkFormDrawer'

export default function SettingsSinksPage() {
  const navigate = useNavigate()
  const { sinks, loading, error, fetchSinks, saveSink, testConfig } = useSinksStore()
  const [editSinkId, setEditSinkId] = useState<string | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [isNewSink, setIsNewSink] = useState(false)
  const editSink = editSinkId ? sinks.find((s) => s.identifier === editSinkId) ?? null : null

  useEffect(() => {
    fetchSinks()
  }, [fetchSinks])

  // Subscribe to WS system channel for setting updates -- auto-refresh on sink config changes
  const sinkHandler = useCallback((event: WsEvent) => {
    const key = (event.payload as Record<string, unknown> | undefined)?.key as string | undefined
    if (key === 'observability/sink_overrides' || key === 'observability/custom_sinks') {
      fetchSinks()
    }
  }, [fetchSinks])

  useWebSocket({
    bindings: [{ channel: 'system', handler: sinkHandler }],
  })

  const handleEdit = useCallback((sink: SinkInfo) => {
    setEditSinkId(sink.identifier)
    setIsNewSink(false)
    setDrawerOpen(true)
  }, [])

  const handleAddNew = useCallback(() => {
    setEditSinkId(null)
    setIsNewSink(true)
    setDrawerOpen(true)
  }, [])

  const handleCloseDrawer = useCallback(() => {
    setDrawerOpen(false)
    setEditSinkId(null)
    setIsNewSink(false)
  }, [])

  const handleSave = useCallback(async (sink: SinkInfo) => {
    await saveSink(sink)
    setDrawerOpen(false)
    setEditSinkId(null)
    setIsNewSink(false)
  }, [saveSink])

  return (
    <div className="space-y-section-gap">
      <div className="flex items-center gap-grid-gap">
        <Button variant="ghost" size="sm" onClick={() => navigate('/settings')}>
          <ArrowLeft className="mr-1.5 size-3.5" aria-hidden />
          Settings
        </Button>
        <div className="flex flex-1 items-center gap-2">
          <Activity className="size-4 text-text-secondary" aria-hidden />
          <h1 className="text-lg font-semibold text-foreground">Log Sinks</h1>
        </div>
        <Button size="sm" onClick={handleAddNew}>
          <Plus className="mr-1.5 size-3.5" aria-hidden />
          Add Sink
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-danger/30 bg-danger/5 p-card text-sm text-danger">
          {error}
        </div>
      )}

      {loading && sinks.length === 0 && (
        <div className="grid grid-cols-1 gap-grid-gap sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-40 rounded-lg" />
          ))}
        </div>
      )}

      {!loading && sinks.length === 0 && !error && (
        <EmptyState
          icon={Activity}
          title="No sinks configured"
          description="Log sinks will appear once the observability system is initialized."
        />
      )}

      <ErrorBoundary level="section">
        <StaggerGroup className="grid grid-cols-1 gap-grid-gap sm:grid-cols-2 lg:grid-cols-3">
          {sinks.map((sink) => (
            <StaggerItem key={sink.identifier}>
              <SinkCard sink={sink} onEdit={handleEdit} />
            </StaggerItem>
          ))}
        </StaggerGroup>
      </ErrorBoundary>

      <SinkFormDrawer
        key={editSink?.identifier ?? (isNewSink ? '__new__' : '__closed__')}
        open={drawerOpen}
        onClose={handleCloseDrawer}
        sink={editSink}
        isNew={isNewSink}
        onTest={testConfig}
        onSave={handleSave}
      />
    </div>
  )
}
