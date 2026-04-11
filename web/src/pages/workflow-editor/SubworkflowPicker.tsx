import { useCallback, useEffect, useRef, useState } from 'react'
import { Dialog } from '@base-ui/react/dialog'
import { Layers, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { InputField } from '@/components/ui/input-field'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { listSubworkflows, searchSubworkflows, listVersions } from '@/api/endpoints/subworkflows'
import { createLogger } from '@/lib/logger'
import { sanitizeForLog } from '@/utils/logging'
import { getErrorMessage } from '@/utils/errors'
import { useToastStore } from '@/stores/toast'
import type { SubworkflowSummary } from '@/api/types'

const log = createLogger('SubworkflowPicker')

interface SubworkflowPickerProps {
  open: boolean
  onClose: () => void
  onSelect: (subworkflowId: string, version: string) => void
}

export function SubworkflowPicker({ open, onClose, onSelect }: SubworkflowPickerProps) {
  const addToast = useToastStore((s) => s.add)
  const [query, setQuery] = useState('')
  const [summaries, setSummaries] = useState<readonly SubworkflowSummary[]>([])
  const [versions, setVersions] = useState<readonly string[]>([])
  const [selectedSub, setSelectedSub] = useState<SubworkflowSummary | null>(null)
  const [selectedVersion, setSelectedVersion] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [versionsLoading, setVersionsLoading] = useState(false)
  const versionsRequestIdRef = useRef(0)

  useEffect(() => {
    if (!open) return
    let cancelled = false
    async function load() {
      setLoading(true)
      try {
        const q = query.trim()
        const results = q ? await searchSubworkflows(q) : await listSubworkflows()
        if (!cancelled) setSummaries(results)
      } catch (err: unknown) {
        if (!cancelled) {
          log.warn('Failed to load subworkflows', sanitizeForLog(err))
          addToast({ variant: 'error', title: 'Failed to load subworkflows', description: getErrorMessage(err) })
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => { cancelled = true }
  }, [open, query, addToast])

  const handleSubSelect = useCallback(async (sub: SubworkflowSummary) => {
    const requestId = ++versionsRequestIdRef.current
    setSelectedSub(sub)
    setSelectedVersion(sub.latest_version)
    setVersionsLoading(true)
    try {
      const vers = await listVersions(sub.subworkflow_id)
      if (requestId !== versionsRequestIdRef.current) return
      setVersions(vers)
    } catch (err: unknown) {
      if (requestId !== versionsRequestIdRef.current) return
      log.warn('Failed to load versions', sanitizeForLog(err))
      setVersions([sub.latest_version])
    } finally {
      if (requestId === versionsRequestIdRef.current) setVersionsLoading(false)
    }
  }, [])

  const handleConfirm = useCallback(() => {
    if (!selectedSub || !selectedVersion) return
    onSelect(selectedSub.subworkflow_id, selectedVersion)
    onClose()
  }, [selectedSub, selectedVersion, onSelect, onClose])

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      if (!nextOpen) {
        onClose()
        setQuery('')
        setSelectedSub(null)
        setSelectedVersion('')
        setVersions([])
      }
    },
    [onClose],
  )

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm transition-opacity data-[closed]:opacity-0 data-[starting-style]:opacity-0" />
        <Dialog.Popup className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-lg border border-border bg-card shadow-xl">
            <div className="flex items-center justify-between border-b border-border p-card">
              <Dialog.Title className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <Layers className="size-4 text-accent" aria-hidden="true" />
                Select Subworkflow
              </Dialog.Title>
              <Dialog.Close
                render={<button type="button" className="rounded p-1 text-muted-foreground hover:text-foreground" aria-label="Close" />}
              >
                <X className="size-4" />
              </Dialog.Close>
            </div>

            <div className="space-y-section-gap p-card">
              <InputField
                label="Search"
                value={query}
                onValueChange={setQuery}
                placeholder="Search by name or ID..."
                type="text"
              />

              <div className="max-h-64 overflow-y-auto">
                {loading ? (
                  <div className="flex flex-col gap-2" role="status" aria-label="Loading subworkflows">
                    {Array.from({ length: 3 }, (_, i) => (
                      <Skeleton key={i} className="h-12 rounded-lg" />
                    ))}
                  </div>
                ) : summaries.length === 0 ? (
                  <EmptyState title="No subworkflows" description="No subworkflows found in the registry." />
                ) : (
                  <ul className="flex flex-col gap-1" role="listbox" aria-label="Subworkflows">
                    {summaries.map((s) => (
                      <li key={s.subworkflow_id}>
                        <button
                          type="button"
                          role="option"
                          aria-selected={selectedSub?.subworkflow_id === s.subworkflow_id}
                          className={`flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm transition-colors ${
                            selectedSub?.subworkflow_id === s.subworkflow_id
                              ? 'bg-accent/10 text-accent'
                              : 'text-foreground hover:bg-accent/5'
                          }`}
                          onClick={() => void handleSubSelect(s)}
                        >
                          <div className="min-w-0">
                            <span className="font-medium">{s.name}</span>
                            <span className="ml-2 text-xs text-muted-foreground">
                              {s.input_count}in / {s.output_count}out
                            </span>
                          </div>
                          <span className="shrink-0 rounded-sm bg-accent/10 px-1.5 py-0.5 text-xs text-accent">
                            v{s.latest_version}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {selectedSub && (
                <div className="flex items-center gap-2">
                  <label htmlFor="version-select" className="text-xs font-medium text-foreground">
                    Version:
                  </label>
                  {versionsLoading ? (
                    <Skeleton className="h-8 w-24 rounded" />
                  ) : (
                    <select
                      id="version-select"
                      className="rounded-md border border-border bg-card px-2 py-1 text-xs text-foreground"
                      value={selectedVersion}
                      onChange={(e) => setSelectedVersion(e.target.value)}
                    >
                      {versions.map((v) => (
                        <option key={v} value={v}>v{v}</option>
                      ))}
                    </select>
                  )}
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 border-t border-border p-card">
              <Dialog.Close render={<Button variant="ghost" size="sm">Cancel</Button>} />
              <Button
                size="sm"
                onClick={handleConfirm}
                disabled={!selectedSub || !selectedVersion}
              >
                Select
              </Button>
            </div>
          </div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
