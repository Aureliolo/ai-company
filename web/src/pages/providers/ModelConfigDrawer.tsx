import { useState } from 'react'
import { Drawer } from '@/components/ui/drawer'
import { InputField } from '@/components/ui/input-field'
import { Button } from '@/components/ui/button'
import { useProvidersStore } from '@/stores/providers'
import type { LocalModelParams, ProviderModelResponse } from '@/api/types/providers'

interface ModelConfigDrawerProps {
  providerName: string
  model: ProviderModelResponse | null
  open: boolean
  onClose: () => void
}

function ModelConfigForm({
  providerName,
  model,
  onClose,
}: {
  providerName: string
  model: ProviderModelResponse
  onClose: () => void
}) {
  const updateModelConfig = useProvidersStore((s) => s.updateModelConfig)
  const params = model.local_params

  const [numCtx, setNumCtx] = useState(params?.num_ctx?.toString() ?? '')
  const [numGpuLayers, setNumGpuLayers] = useState(params?.num_gpu_layers?.toString() ?? '')
  const [numThreads, setNumThreads] = useState(params?.num_threads?.toString() ?? '')
  const [numBatch, setNumBatch] = useState(params?.num_batch?.toString() ?? '')
  const [repeatPenalty, setRepeatPenalty] = useState(params?.repeat_penalty?.toString() ?? '')
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    const parseIntStrict = (val: string): number | null => {
      const s = val.trim()
      if (!s) return null
      const n = Number(s)
      return Number.isFinite(n) && Number.isInteger(n) ? n : null
    }
    const parseFloatStrict = (val: string): number | null => {
      const s = val.trim()
      if (!s) return null
      const n = Number(s)
      return Number.isFinite(n) ? n : null
    }
    const newParams: LocalModelParams = {
      num_ctx: parseIntStrict(numCtx),
      num_gpu_layers: parseIntStrict(numGpuLayers),
      num_threads: parseIntStrict(numThreads),
      num_batch: parseIntStrict(numBatch),
      repeat_penalty: parseFloatStrict(repeatPenalty),
    }
    const success = await updateModelConfig(providerName, model.id, newParams)
    setSaving(false)
    if (success) onClose()
  }

  return (
    <div className="flex flex-col gap-section-gap">
      <InputField
        label="Context window (num_ctx)"
        value={numCtx}
        onValueChange={setNumCtx}
        placeholder="e.g. 4096"
        hint="Context window size in tokens"
      />
      <InputField
        label="GPU layers (num_gpu_layers)"
        value={numGpuLayers}
        onValueChange={setNumGpuLayers}
        placeholder="e.g. 32"
        hint="Number of layers to offload to GPU (0 = CPU only)"
      />
      <InputField
        label="CPU threads (num_threads)"
        value={numThreads}
        onValueChange={setNumThreads}
        placeholder="auto"
        hint="Number of CPU threads"
      />
      <InputField
        label="Batch size (num_batch)"
        value={numBatch}
        onValueChange={setNumBatch}
        placeholder="512"
        hint="Batch size for prompt processing"
      />
      <InputField
        label="Repetition penalty (repeat_penalty)"
        value={repeatPenalty}
        onValueChange={setRepeatPenalty}
        placeholder="1.1"
        hint="Penalize repeated tokens (1.0 = disabled)"
      />
      <div className="flex justify-end gap-2 pt-2">
        <Button variant="outline" size="sm" onClick={onClose} disabled={saving}>
          Cancel
        </Button>
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save'}
        </Button>
      </div>
    </div>
  )
}

export function ModelConfigDrawer({ providerName, model, open, onClose }: ModelConfigDrawerProps) {
  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={model ? `Configure ${model.id}` : 'Configure Model'}
    >
      {model && (
        <ModelConfigForm
          key={model.id}
          providerName={providerName}
          model={model}
          onClose={onClose}
        />
      )}
    </Drawer>
  )
}
