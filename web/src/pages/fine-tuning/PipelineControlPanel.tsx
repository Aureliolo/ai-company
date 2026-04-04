import { useState } from 'react'

import { ACTIVE_STAGES } from '@/api/endpoints/fine-tuning'
import type { StartFineTuneRequest } from '@/api/endpoints/fine-tuning'
import { Button } from '@/components/ui/button'
import { InputField } from '@/components/ui/input-field'
import { useFineTuningStore } from '@/stores/fine-tuning'

import { PreflightResultPanel } from './PreflightResultPanel'

export function PipelineControlPanel() {
  const { status, preflight, loading, startRun, cancelRun, runPreflightCheck } =
    useFineTuningStore()
  const [sourceDir, setSourceDir] = useState('/data/documents')
  const [showAdvanced, setShowAdvanced] = useState(false)

  const isActive = status != null && ACTIVE_STAGES.has(status.stage)

  const handlePreflight = () => {
    const request: StartFineTuneRequest = { source_dir: sourceDir }
    void runPreflightCheck(request)
  }

  const handleStart = () => {
    const request: StartFineTuneRequest = { source_dir: sourceDir }
    void startRun(request)
  }

  return (
    <div className="flex flex-col gap-section-gap">
      <div className="flex items-end gap-4">
        <InputField
          label="Source Directory"
          value={sourceDir}
          onValueChange={setSourceDir}
          hint="Directory containing org documents for training"
        />
        <div className="flex gap-2 pb-1">
          <Button variant="outline" onClick={handlePreflight} disabled={loading}>
            Pre-flight Check
          </Button>
          {isActive ? (
            <Button variant="destructive" onClick={() => void cancelRun()}>
              Cancel
            </Button>
          ) : (
            <Button
              onClick={handleStart}
              disabled={loading || (preflight != null && !preflight.can_proceed)}
            >
              Start Fine-Tuning
            </Button>
          )}
        </div>
      </div>

      {preflight && <PreflightResultPanel result={preflight} />}

      <button
        type="button"
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="self-start text-sm text-muted-foreground hover:text-foreground"
      >
        {showAdvanced ? 'Hide' : 'Show'} Advanced Options
      </button>

      {showAdvanced && (
        <div className="grid grid-cols-3 gap-grid-gap rounded-lg border border-border p-card">
          <InputField label="Epochs" value="3" onChange={() => {}} hint="Training epochs" />
          <InputField label="Learning Rate" value="1e-5" onChange={() => {}} />
          <InputField label="Batch Size" value={String(preflight?.recommended_batch_size ?? 128)} onChange={() => {}} />
        </div>
      )}
    </div>
  )
}
