import { useCallback, useEffect, useRef, useState } from 'react'
import { useShallow } from 'zustand/react/shallow'

import { ACTIVE_STAGES } from '@/api/endpoints/fine-tuning'
import type { StartFineTuneRequest } from '@/api/endpoints/fine-tuning'
import { Button } from '@/components/ui/button'
import { InputField } from '@/components/ui/input-field'
import { useFineTuningStore } from '@/stores/fine-tuning'

import { PreflightResultPanel } from './PreflightResultPanel'

export function PipelineControlPanel() {
  const { status, preflight, loading, startRun, cancelRun, runPreflightCheck } =
    useFineTuningStore(useShallow((s) => ({
      status: s.status,
      preflight: s.preflight,
      loading: s.loading,
      startRun: s.startRun,
      cancelRun: s.cancelRun,
      runPreflightCheck: s.runPreflightCheck,
    })))
  const [sourceDir, setSourceDir] = useState('/data/documents')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [epochs, setEpochs] = useState('')
  const [learningRate, setLearningRate] = useState('')
  const batchSizeTouchedRef = useRef(false)
  const [batchSizeInput, setBatchSizeInput] = useState('')
  const setBatchSize = useCallback((value: string) => {
    batchSizeTouchedRef.current = true
    setBatchSizeInput(value)
  }, [])

  // When preflight arrives with a recommended batch size and the user hasn't
  // typed a value yet, use it as the initial value.
  const recommendedBatch = preflight?.recommended_batch_size
  const effectiveBatchSize =
    !batchSizeTouchedRef.current && batchSizeInput === '' && recommendedBatch != null
      ? String(recommendedBatch)
      : batchSizeInput

  // Clear stale preflight when sourceDir changes.
  useEffect(() => {
    useFineTuningStore.setState({ preflight: null })
  }, [sourceDir])

  const isActive = status != null && ACTIVE_STAGES.has(status.stage)

  const buildRequest = (): StartFineTuneRequest => {
    const request: StartFineTuneRequest = { source_dir: sourceDir }
    if (showAdvanced) {
      if (epochs !== '') {
        const parsedEpochs = Number(epochs)
        if (!Number.isNaN(parsedEpochs) && parsedEpochs > 0) request.epochs = parsedEpochs
      }
      if (learningRate !== '') {
        const parsedLr = Number(learningRate)
        if (!Number.isNaN(parsedLr) && parsedLr > 0) request.learning_rate = parsedLr
      }
      if (effectiveBatchSize !== '') {
        const parsedBatch = Number(effectiveBatchSize)
        if (!Number.isNaN(parsedBatch) && parsedBatch > 0) request.batch_size = parsedBatch
      }
    }
    return request
  }

  const handlePreflight = () => {
    void runPreflightCheck(buildRequest())
  }

  const handleStart = () => {
    void startRun(buildRequest())
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

      <Button
        variant="ghost"
        size="sm"
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="self-start"
        aria-expanded={showAdvanced}
        aria-controls="advanced-options-panel"
      >
        {showAdvanced ? 'Hide' : 'Show'} Advanced Options
      </Button>

      {showAdvanced && (
        <div
          id="advanced-options-panel"
          className="grid grid-cols-3 gap-grid-gap rounded-lg border border-border p-card"
        >
          <InputField label="Epochs" value={epochs} onValueChange={setEpochs} hint="Training epochs" />
          <InputField label="Learning Rate" value={learningRate} onValueChange={setLearningRate} />
          <InputField label="Batch Size" value={effectiveBatchSize} onValueChange={setBatchSize} />
        </div>
      )}
    </div>
  )
}
