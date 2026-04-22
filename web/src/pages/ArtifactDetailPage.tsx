import { useEffect, useRef } from 'react'
import { useParams } from 'react-router'
import { useArtifactDetailData } from '@/hooks/useArtifactDetailData'
import { Breadcrumbs } from '@/components/ui/breadcrumbs'
import { ErrorBanner } from '@/components/ui/error-banner'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { ROUTES } from '@/router/routes'
import { ArtifactDetailSkeleton } from './artifacts/ArtifactDetailSkeleton'
import { ArtifactMetadata } from './artifacts/ArtifactMetadata'
import { ArtifactContentPreview } from './artifacts/ArtifactContentPreview'

export default function ArtifactDetailPage() {
  const { artifactId } = useParams<{ artifactId: string }>()
  const {
    artifact,
    contentPreview,
    loading,
    error,
    wsConnected,
    wsSetupError,
  } = useArtifactDetailData(artifactId ?? '')

  // Only surface the "real-time updates disconnected" banner once we've
  // successfully connected at least once; otherwise the initial handshake
  // flashes a false-positive offline banner before the socket is ready.
  const hasEverConnectedRef = useRef(false)
  useEffect(() => {
    if (wsConnected) hasEverConnectedRef.current = true
  }, [wsConnected])

  if (loading && !artifact) {
    return <ArtifactDetailSkeleton />
  }

  if (!artifact) {
    return (
      <div className="space-y-section-gap">
        <Breadcrumbs items={[{ label: 'Artifacts', to: ROUTES.ARTIFACTS }, { label: 'Unknown artifact' }]} />
        <ErrorBanner severity="error" title="Artifact not found" description={error ?? undefined} />
      </div>
    )
  }

  return (
    <div className="space-y-section-gap">
      <Breadcrumbs items={[{ label: 'Artifacts', to: ROUTES.ARTIFACTS }, { label: artifact.id }]} />

      {error && (
        <ErrorBanner severity="error" title="Could not load artifact" description={error} />
      )}

      {!wsConnected && !loading && hasEverConnectedRef.current && (
        <ErrorBanner
          variant="offline"
          title="Real-time updates disconnected"
          description={wsSetupError ?? 'Data may be stale until the connection recovers.'}
        />
      )}

      <ErrorBoundary level="section">
        <ArtifactMetadata artifact={artifact} />
      </ErrorBoundary>

      <ErrorBoundary level="section">
        <ArtifactContentPreview artifact={artifact} contentPreview={contentPreview} />
      </ErrorBoundary>
    </div>
  )
}
