import { useEffect, useState } from 'react'
import { Eye } from 'lucide-react'
import { SectionCard } from '@/components/ui/section-card'
import { EmptyState } from '@/components/ui/empty-state'
import { LazyCodeMirrorEditor } from '@/components/ui/lazy-code-mirror-editor'
import { downloadArtifactContent } from '@/api/endpoints/artifacts'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/errors'
import type { Artifact } from '@/api/types'

interface ArtifactContentPreviewProps {
  artifact: Artifact
  contentPreview: string | null
}

function getLanguage(contentType: string): 'json' | 'yaml' {
  if (contentType === 'application/json') return 'json'
  if (contentType === 'application/x-yaml' || contentType === 'text/yaml') return 'yaml'
  // Default to JSON for syntax highlighting even for plain text
  return 'json'
}

const NOOP = () => {}

export function ArtifactContentPreview({ artifact, contentPreview }: ArtifactContentPreviewProps) {
  const [imageSrc, setImageSrc] = useState<string | null>(null)

  const isImage = artifact.content_type?.startsWith('image/')
  const isText = contentPreview !== null

  // Load image as blob URL for image content types
  useEffect(() => {
    if (!isImage || artifact.size_bytes === 0) return
    let revoked = false
    downloadArtifactContent(artifact.id)
      .then((blob) => {
        if (revoked) return
        setImageSrc(URL.createObjectURL(blob))
      })
      .catch(() => {
        // Best-effort image preview
      })
    return () => {
      revoked = true
      if (imageSrc) URL.revokeObjectURL(imageSrc)
    }
    // Only re-run when artifact changes
    // eslint-disable-next-line @eslint-react/exhaustive-deps
  }, [artifact.id, isImage, artifact.size_bytes])

  if (artifact.size_bytes === 0) {
    return (
      <SectionCard title="Content">
        <EmptyState
          icon={Eye}
          title="No content uploaded"
          description="This artifact has no stored content."
        />
      </SectionCard>
    )
  }

  async function handleDownload() {
    try {
      const blob = await downloadArtifactContent(artifact.id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = artifact.path.split('/').pop() ?? artifact.id
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      useToastStore.getState().add({
        variant: 'error',
        title: 'Download failed',
        description: getErrorMessage(err),
      })
    }
  }

  if (isText) {
    return (
      <SectionCard title="Content Preview">
        <LazyCodeMirrorEditor
          value={contentPreview}
          onChange={NOOP}
          language={getLanguage(artifact.content_type)}
          readOnly
        />
      </SectionCard>
    )
  }

  if (isImage && imageSrc) {
    return (
      <SectionCard title="Content Preview">
        <img
          src={imageSrc}
          alt={`Preview of ${artifact.path}`}
          className="max-h-96 rounded-md border border-border object-contain"
        />
      </SectionCard>
    )
  }

  return (
    <SectionCard title="Content">
      <EmptyState
        icon={Eye}
        title="Preview not available"
        description={`Content type: ${artifact.content_type || 'unknown'}`}
        action={{ label: 'Download', onClick: handleDownload }}
      />
    </SectionCard>
  )
}
