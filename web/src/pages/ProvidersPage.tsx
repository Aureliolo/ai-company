import { useState } from 'react'
import { Plus } from 'lucide-react'
import { useProvidersData } from '@/hooks/useProvidersData'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { ErrorBanner } from '@/components/ui/error-banner'
import { ListHeader } from '@/components/ui/list-header'
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
      <ListHeader
        title="Providers"
        count={providers.length}
        primaryAction={
          <Button size="sm" onClick={() => setDrawerOpen(true)}>
            <Plus className="size-3.5 mr-1.5" />
            Add Provider
          </Button>
        }
      />

      {error && (
        <ErrorBanner
          severity="error"
          title="Could not load providers"
          description={error}
        />
      )}

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
