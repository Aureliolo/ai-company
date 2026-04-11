import { useCallback, useEffect, useState } from 'react'
import { Dialog } from '@base-ui/react/dialog'
import { ArrowRight, GitBranch, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { listVersions } from '@/api/endpoints/subworkflows'
import { createLogger } from '@/lib/logger'
import { sanitizeForLog } from '@/utils/logging'
import type { SubworkflowSummary } from '@/api/types'

const log = createLogger('SubworkflowUpdateModal')

interface SubworkflowUpdateModalProps {
  open: boolean
  onClose: () => void
  subworkflow: SubworkflowSummary
  currentPinnedVersion: string
  onRepin: (newVersion: string) => void
}

export function SubworkflowUpdateModal({
  open,
  onClose,
  subworkflow,
  currentPinnedVersion,
  onRepin,
}: SubworkflowUpdateModalProps) {
  const [versions, setVersions] = useState<readonly string[]>([])
  const [selectedVersion, setSelectedVersion] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    let cancelled = false
    async function load() {
      setLoading(true)
      setVersions([])
      setSelectedVersion('')
      try {
        const vers = await listVersions(subworkflow.subworkflow_id)
        if (!cancelled) {
          // API returns newest first -- only allow versions that
          // appear before the current pin (i.e. strictly newer).
          const currentIdx = vers.indexOf(currentPinnedVersion)
          const candidates = currentIdx > 0 ? vers.slice(0, currentIdx) : []
          setVersions(candidates)
          setSelectedVersion(candidates[0] ?? '')
        }
      } catch (err: unknown) {
        if (!cancelled) {
          log.warn('Failed to load versions', sanitizeForLog(err))
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => { cancelled = true }
  }, [open, subworkflow.subworkflow_id, currentPinnedVersion])

  const newerVersions = versions

  const handleConfirm = useCallback(() => {
    if (loading || !newerVersions.includes(selectedVersion)) return
    onRepin(selectedVersion)
    onClose()
  }, [loading, newerVersions, selectedVersion, onRepin, onClose])

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      if (!nextOpen) onClose()
    },
    [onClose],
  )

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm transition-opacity data-[closed]:opacity-0 data-[starting-style]:opacity-0" />
        <Dialog.Popup className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-lg border border-border bg-card shadow-xl">
            <div className="flex items-center justify-between border-b border-border p-card">
              <Dialog.Title className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <GitBranch className="size-4 text-accent" aria-hidden="true" />
                Update Pinned Version
              </Dialog.Title>
              <Dialog.Close
                render={<button type="button" className="rounded p-1 text-muted-foreground hover:text-foreground" aria-label="Close" />}
              >
                <X className="size-4" />
              </Dialog.Close>
            </div>

            <div className="space-y-section-gap p-card">
              <div className="text-xs text-muted-foreground">
                <span className="font-medium text-foreground">{subworkflow.name}</span>
                {' '}is currently pinned at{' '}
                <span className="rounded-sm bg-accent/10 px-1 py-px font-medium text-accent">
                  v{currentPinnedVersion}
                </span>
              </div>

              {loading ? (
                <div className="flex flex-col gap-2" role="status" aria-label="Loading versions">
                  <Skeleton className="h-8 rounded" />
                  <Skeleton className="h-8 rounded" />
                </div>
              ) : newerVersions.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No other versions available. Already on the latest version.
                </p>
              ) : (
                <div className="flex flex-col gap-1">
                  <label className="text-xs font-medium text-foreground">
                    Select new version:
                  </label>
                  <ul className="flex flex-col gap-1" role="radiogroup" aria-label="Available versions">
                    {newerVersions.map((v) => (
                      <li key={v}>
                        <button
                          type="button"
                          role="radio"
                          aria-checked={selectedVersion === v}
                          className={`flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-xs transition-colors ${
                            selectedVersion === v
                              ? 'bg-accent/10 text-accent'
                              : 'text-foreground hover:bg-accent/5'
                          }`}
                          onClick={() => setSelectedVersion(v)}
                        >
                          <span className="rounded-sm bg-accent/10 px-1 py-px font-medium">
                            v{v}
                          </span>
                          {selectedVersion === v && (
                            <ArrowRight className="size-3 text-accent" aria-hidden="true" />
                          )}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 border-t border-border p-card">
              <Dialog.Close render={<Button variant="ghost" size="sm">Cancel</Button>} />
              <Button
                size="sm"
                onClick={handleConfirm}
                disabled={loading || !newerVersions.includes(selectedVersion)}
              >
                Re-pin to v{selectedVersion || '...'}
              </Button>
            </div>
          </div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
