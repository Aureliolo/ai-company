import { useState } from 'react'
import { AlertDialog } from '@base-ui/react/alert-dialog'
import { Button } from '@/components/ui/button'
import { InputField } from '@/components/ui/input-field'
import { ProgressGauge } from '@/components/ui/progress-gauge'
import { LiveRegion } from '@/components/ui/live-region'
import { useProvidersStore } from '@/stores/providers'
import { Download } from 'lucide-react'

interface ModelPullDialogProps {
  providerName: string
  open: boolean
  onClose: () => void
}

export function ModelPullDialog({ providerName, open, onClose }: ModelPullDialogProps) {
  const [modelName, setModelName] = useState('')
  const pullingModel = useProvidersStore((s) => s.pullingModel)
  const pullProgress = useProvidersStore((s) => s.pullProgress)
  const pullModel = useProvidersStore((s) => s.pullModel)
  const cancelPull = useProvidersStore((s) => s.cancelPull)

  // Two-phase close: while a pull is in flight we only dispatch the cancel
  // action (which asks the store to abort the pull). The dialog stays open
  // until the store clears `pullingModel`, at which point the next
  // onOpenChange(false) (triggered by the user or by pullingModel becoming
  // null) falls through to `onClose()`. This is intentional UX -- we surface
  // the "cancelling..." state in the progress region rather than snapping
  // the dialog shut while the backend is still tearing down the pull.
  const handleCancel = () => {
    if (pullingModel) {
      cancelPull()
    } else {
      onClose()
    }
  }

  const handlePull = async () => {
    if (!modelName.trim()) return
    const success = await pullModel(providerName, modelName.trim())
    if (success) {
      setModelName('')
      onClose()
    }
  }

  const progressPercent = pullProgress?.progress_percent ?? 0
  const statusText = pullProgress?.status ?? ''

  return (
    <AlertDialog.Root open={open} onOpenChange={(isOpen: boolean) => { if (!isOpen) handleCancel() }}>
      <AlertDialog.Portal>
        <AlertDialog.Backdrop className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm transition-opacity duration-200 ease-out data-[closed]:opacity-0 data-[starting-style]:opacity-0 data-[ending-style]:opacity-0" />
        <AlertDialog.Popup
          className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg bg-card p-card shadow-lg transition-[opacity,translate,scale] duration-200 ease-out data-[closed]:opacity-0 data-[starting-style]:opacity-0 data-[ending-style]:opacity-0 data-[closed]:scale-95 data-[starting-style]:scale-95 data-[ending-style]:scale-95"
          aria-label="Pull model"
        >
          <AlertDialog.Title className="text-lg font-semibold text-foreground">
            Pull Model
          </AlertDialog.Title>

          {!pullingModel ? (
            <div className="mt-4 flex flex-col gap-section-gap">
              <AlertDialog.Description className="sr-only">
                Enter a model name to pull from the provider.
              </AlertDialog.Description>
              <InputField
                label="Model name"
                value={modelName}
                onValueChange={setModelName}
                placeholder="e.g. llama3.2:1b"
                hint="Enter the model name and optional tag"
              />
              <div className="flex justify-end gap-2">
                <AlertDialog.Close
                  render={
                    <Button variant="outline" size="sm">
                      Cancel
                    </Button>
                  }
                />
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
            <div className="mt-4 flex flex-col gap-section-gap">
              <AlertDialog.Description className="sr-only">
                Model download in progress.
              </AlertDialog.Description>
              <div className="flex items-center justify-center py-4">
                <ProgressGauge
                  value={progressPercent}
                  variant="linear"
                />
              </div>
              <LiveRegion>
                <p className="text-center text-sm text-text-secondary truncate">
                  {statusText}
                </p>
                {pullProgress?.error && (
                  <p className="text-center text-sm text-danger">
                    {pullProgress.error}
                  </p>
                )}
              </LiveRegion>
              <div className="flex justify-end">
                <Button variant="outline" size="sm" onClick={handleCancel}>
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </AlertDialog.Popup>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  )
}
