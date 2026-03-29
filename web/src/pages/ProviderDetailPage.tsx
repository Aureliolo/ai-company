import { useState } from 'react'
import { useParams, useNavigate } from 'react-router'
import { useProviderDetailData } from '@/hooks/useProviderDetailData'
import { useProvidersStore } from '@/stores/providers'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { EmptyState } from '@/components/ui/empty-state'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { ROUTES } from '@/router/routes'
import { ProviderDetailHeader } from './providers/ProviderDetailHeader'
import { ProviderHealthMetrics } from './providers/ProviderHealthMetrics'
import { ProviderModelList } from './providers/ProviderModelList'
import { ProviderDetailSkeleton } from './providers/ProviderDetailSkeleton'
import { ProviderFormModal } from './providers/ProviderFormModal'
import { TestConnectionResult } from './providers/TestConnectionResult'
import { Server } from 'lucide-react'

export default function ProviderDetailPage() {
  const { providerName } = useParams<{ providerName: string }>()
  const navigate = useNavigate()
  const decodedName = providerName ?? ''

  const {
    provider,
    models,
    health,
    loading,
    error,
    testConnectionResult,
    testingConnection,
  } = useProviderDetailData(decodedName)

  const [editOpen, setEditOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)

  // Loading state
  if (loading && !provider) {
    return <ProviderDetailSkeleton />
  }

  // Error state
  if (error && !provider) {
    return (
      <div className="flex flex-col gap-4">
        <div className="rounded-md bg-danger/10 px-4 py-3 text-sm text-danger">
          {error}
        </div>
      </div>
    )
  }

  if (!provider) {
    return (
      <EmptyState
        icon={Server}
        title="Provider not found"
        description="The provider you are looking for does not exist or has been removed."
        action={{ label: 'Back to Providers', onClick: () => navigate(ROUTES.PROVIDERS) }}
      />
    )
  }

  return (
    <div className="flex flex-col gap-section-gap">
      {/* Partial error banner */}
      {error && (
        <div className="rounded-md bg-warning/10 px-4 py-3 text-sm text-warning">
          {error}
        </div>
      )}

      {/* Header */}
      <ErrorBoundary level="section">
        <ProviderDetailHeader
          provider={provider}
          health={health}
          onEdit={() => setEditOpen(true)}
          onDelete={() => setDeleteOpen(true)}
          onTestConnection={() => {
            useProvidersStore.getState().testConnection(decodedName)
          }}
          testingConnection={testingConnection}
        />
      </ErrorBoundary>

      {/* Test connection result */}
      {testConnectionResult && (
        <TestConnectionResult result={testConnectionResult} />
      )}

      {/* Health metrics */}
      {health && (
        <ErrorBoundary level="section">
          <ProviderHealthMetrics health={health} />
        </ErrorBoundary>
      )}

      {/* Model list */}
      <ErrorBoundary level="section">
        <ProviderModelList models={models} />
      </ErrorBoundary>

      {/* Edit drawer */}
      <ProviderFormModal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        mode="edit"
        provider={provider}
      />

      {/* Delete confirmation */}
      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Delete Provider"
        description={`Are you sure you want to delete "${provider.name}"? This action cannot be undone.`}
        variant="destructive"
        confirmLabel="Delete"
        onConfirm={async () => {
          const success = await useProvidersStore.getState().deleteProvider(decodedName)
          if (success) {
            navigate(ROUTES.PROVIDERS)
          }
          setDeleteOpen(false)
        }}
      />
    </div>
  )
}
