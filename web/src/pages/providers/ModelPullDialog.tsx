import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { InputField } from '@/components/ui/input-field'
import { ProgressGauge } from '@/components/ui/progress-gauge'
import { useProvidersStore } from '@/stores/providers'
import { Download, X } from 'lucide-react'

interface ModelPullDialogProps {
  providerName: string
  open: boolean
  onClose: () => void
}

export function ModelPullDialog({ providerName, open, onClose }: ModelPullDialogProps) {
  const [modelName, setModelName] = useState('')
  const { pullingModel, pullProgress, pullModel, cancelPull } = useProvidersStore()

  if (!open) return null

  const handlePull = async () => {
    if (!modelName.trim()) return
    const success = await pullModel(providerName, modelName.trim())
    if (success) {
      setModelName('')
      onClose()
    }
  }

  const handleCancel = () => {
    if (pullingModel) {
      cancelPull()
    } else {
      onClose()
    }
  }

  const progressPercent = pullProgress?.progress_percent ?? 0
  const statusText = pullProgress?.status ?? ''

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg bg-card p-card shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">Pull Model</h2>
          <button
            type="button"
            onClick={handleCancel}
            className="rounded p-1 text-text-muted hover:bg-bg-surface hover:text-foreground transition-colors"
          >
            <X className="size-4" />
          </button>
        </div>

        {!pullingModel ? (
          <div className="flex flex-col gap-4">
            <InputField
              label="Model name"
              value={modelName}
              onValueChange={setModelName}
              placeholder="e.g. llama3.2:1b"
              hint="Enter the model name and optional tag"
            />
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={onClose}>
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handlePull}
                disabled={!modelName.trim()}
              >
                <Download className="size-3.5 mr-1.5" />
                Pull
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-center py-4">
              <ProgressGauge
                value={progressPercent}
                variant="linear"
              />
            </div>
            <p className="text-center text-sm text-text-secondary truncate">
              {statusText}
            </p>
            {pullProgress?.error && (
              <p className="text-center text-sm text-danger">
                {pullProgress.error}
              </p>
            )}
            <div className="flex justify-end">
              <Button variant="outline" size="sm" onClick={handleCancel}>
                Cancel
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
