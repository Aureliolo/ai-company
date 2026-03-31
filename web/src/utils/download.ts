import { downloadArtifactContent } from '@/api/endpoints/artifacts'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/errors'

/**
 * Download artifact content as a file via a temporary anchor element.
 *
 * Shows an error toast on failure.
 */
export async function downloadArtifactFile(artifactId: string, fallbackName: string): Promise<void> {
  try {
    const blob = await downloadArtifactContent(artifactId)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fallbackName
    try {
      document.body.appendChild(a)
      a.click()
    } finally {
      if (a.parentNode) document.body.removeChild(a)
      URL.revokeObjectURL(url)
    }
  } catch (err) {
    useToastStore.getState().add({
      variant: 'error',
      title: 'Download failed',
      description: getErrorMessage(err),
    })
  }
}
