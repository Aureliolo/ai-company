import { useEffect, useState } from 'react'
import { Plug, Plus } from 'lucide-react'
import type { Connection } from '@/api/types/integrations'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { useConnectionsData } from '@/hooks/useConnectionsData'
import { useConnectionsStore } from '@/stores/connections'
import { TunnelCard } from './connections/TunnelCard'
import { ConnectionFilters } from './connections/ConnectionFilters'
import { ConnectionFormModal } from './connections/ConnectionFormModal'
import { ConnectionGridView } from './connections/ConnectionGridView'
import { ConnectionsSkeleton } from './connections/ConnectionsSkeleton'

type ModalState =
  | { kind: 'closed' }
  | { kind: 'create' }
  | { kind: 'edit'; connection: Connection }

export default function ConnectionsPage() {
  const { filteredConnections, connections, healthMap, loading, error, checkingHealth } =
    useConnectionsData()
  const runHealthCheck = useConnectionsStore((s) => s.runHealthCheck)
  const deleteConnection = useConnectionsStore((s) => s.deleteConnection)
  const [modal, setModal] = useState<ModalState>({ kind: 'closed' })
  const [pendingDelete, setPendingDelete] = useState<Connection | null>(null)

  useEffect(() => {
    document.title = 'Connections · SynthOrg'
  }, [])

  const hasData = connections.length > 0 || filteredConnections.length > 0

  return (
    <div className="flex flex-col gap-section-gap">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Plug className="size-5 text-text-secondary" aria-hidden />
          <h1 className="text-lg font-semibold text-foreground">Connections</h1>
        </div>
        <Button size="sm" onClick={() => setModal({ kind: 'create' })}>
          <Plus className="mr-1.5 size-3.5" aria-hidden />
          New connection
        </Button>
      </div>

      <TunnelCard />

      {error && (
        <div
          role="alert"
          className="rounded-md bg-danger/10 p-card text-sm text-danger"
        >
          {error}
        </div>
      )}

      <ConnectionFilters />

      {loading && !hasData ? (
        <ConnectionsSkeleton />
      ) : (
        <ErrorBoundary level="section">
          <ConnectionGridView
            connections={filteredConnections}
            healthMap={healthMap}
            checkingHealth={checkingHealth}
            onRunHealthCheck={(name) => void runHealthCheck(name)}
            onEdit={(conn) => setModal({ kind: 'edit', connection: conn })}
            onDelete={(conn) => setPendingDelete(conn)}
            onCreate={() => setModal({ kind: 'create' })}
          />
        </ErrorBoundary>
      )}

      <ConnectionFormModal
        open={modal.kind !== 'closed'}
        mode={modal.kind === 'edit' ? 'edit' : 'create'}
        connection={modal.kind === 'edit' ? modal.connection : null}
        onClose={() => setModal({ kind: 'closed' })}
      />

      <ConfirmDialog
        open={pendingDelete !== null}
        title={`Delete ${pendingDelete?.name ?? ''}?`}
        description="This will permanently remove the connection and its stored credentials. This action cannot be undone."
        confirmLabel="Delete"
        variant="destructive"
        onOpenChange={(next) => {
          if (!next) setPendingDelete(null)
        }}
        onConfirm={async () => {
          if (pendingDelete) {
            await deleteConnection(pendingDelete.name)
            setPendingDelete(null)
          }
        }}
      />
    </div>
  )
}
