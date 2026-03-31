import { useParams, useNavigate } from 'react-router'
import { AlertTriangle, ArrowLeft, WifiOff } from 'lucide-react'
import { useArtifactDetailData } from '@/hooks/useArtifactDetailData'
import { Button } from '@/components/ui/button'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { ROUTES } from '@/router/routes'
import { ArtifactDetailSkeleton } from './artifacts/ArtifactDetailSkeleton'
import { ArtifactMetadata } from './artifacts/ArtifactMetadata'
import { ArtifactContentPreview } from './artifacts/ArtifactContentPreview'

export default function ArtifactDetailPage() {
  const { artifactId } = useParams<{ artifactId: string }>()
  const navigate = useNavigate()
  const {
    artifact,
    contentPreview,
    loading,
    error,
    wsConnected,
    wsSetupError,
  } = useArtifactDetailData(artifactId ?? '')

  if (loading && !artifact) {
    return <ArtifactDetailSkeleton />
  }

  if (!artifact) {
    return (
      <div className="space-y-section-gap">
        <Button variant="ghost" size="sm" onClick={() => navigate(ROUTES.ARTIFACTS)}>
          <ArrowLeft className="mr-1 size-4" />
          Back to Artifacts
        </Button>
        <div
          role="alert"
          className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 p-card text-sm text-danger"
        >
          <AlertTriangle className="size-4 shrink-0" />
          {error ?? 'Artifact not found.'}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-section-gap">
      <Button variant="ghost" size="sm" onClick={() => navigate(ROUTES.ARTIFACTS)}>
        <ArrowLeft className="mr-1 size-4" />
        Back to Artifacts
      </Button>

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

      <ErrorBoundary level="section">
        <ArtifactMetadata artifact={artifact} />
      </ErrorBoundary>

      <ErrorBoundary level="section">
        <ArtifactContentPreview artifact={artifact} contentPreview={contentPreview} />
      </ErrorBoundary>
    </div>
  )
}
