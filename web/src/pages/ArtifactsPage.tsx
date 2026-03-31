import { AlertTriangle, WifiOff } from 'lucide-react'
import { useArtifactsData } from '@/hooks/useArtifactsData'
import { ArtifactsSkeleton } from './artifacts/ArtifactsSkeleton'
import { ArtifactFilters } from './artifacts/ArtifactFilters'
import { ArtifactGridView } from './artifacts/ArtifactGridView'

export default function ArtifactsPage() {
  const {
    filteredArtifacts,
    totalArtifacts,
    loading,
    error,
    wsConnected,
    wsSetupError,
  } = useArtifactsData()

  if (loading && totalArtifacts === 0) {
    return <ArtifactsSkeleton />
  }

  return (
    <div className="space-y-section-gap">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-foreground">Artifacts</h1>
        <span className="text-sm text-muted-foreground">
          {filteredArtifacts.length} of {totalArtifacts}
        </span>
      </div>

      {error && (
        <div
          role="alert"
          aria-live="assertive"
          className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 p-card text-sm text-danger"
        >
          <AlertTriangle className="size-4 shrink-0" />
          {error}
        </div>
      )}

      {!wsConnected && !loading && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 p-card text-sm text-warning"
        >
          <WifiOff className="size-4 shrink-0" />
          {wsSetupError ?? 'Real-time updates disconnected. Data may be stale.'}
        </div>
      )}

      <ArtifactFilters />
      <ArtifactGridView artifacts={filteredArtifacts} />
    </div>
  )
}
