import { useState } from 'react'
import { Plus, Server } from 'lucide-react'
import { useProvidersData } from '@/hooks/useProvidersData'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { Button } from '@/components/ui/button'
import { ProviderGridView } from './providers/ProviderGridView'
import { ProviderFilters } from './providers/ProviderFilters'
import { ProvidersSkeleton } from './providers/ProvidersSkeleton'
import { ProviderFormModal } from './providers/ProviderFormModal'


export default function ProvidersPage() {
  const { filteredProviders, healthMap, loading, error, providers } = useProvidersData()
  const [drawerOpen, setDrawerOpen] = useState(false)

  const hasData = filteredProviders.length > 0 || providers.length > 0

  return (
    <div className="flex flex-col gap-section-gap">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Server className="size-5 text-text-secondary" />
          <h1 className="text-lg font-semibold text-foreground">Providers</h1>
        </div>
        <Button size="sm" onClick={() => setDrawerOpen(true)}>
          <Plus className="size-3.5 mr-1.5" />
          Add Provider
        </Button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="rounded-md bg-danger/10 px-4 py-3 text-sm text-danger">
          {error}
        </div>
      )}

      {/* Filters */}
      <ProviderFilters />

      {/* Content */}
      {loading && !hasData ? (
        <ProvidersSkeleton />
      ) : (
        <ErrorBoundary level="section">
          <ProviderGridView
            providers={filteredProviders}
            healthMap={healthMap}
            onAddProvider={() => setDrawerOpen(true)}
          />
        </ErrorBoundary>
      )}

      {/* Create drawer */}
      <ProviderFormModal
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        mode="create"
      />
    </div>
  )
}
