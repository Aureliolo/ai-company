import { useMemo } from 'react'
import { SelectField } from '@/components/ui/select-field'
import type { SelectOption } from '@/components/ui/select-field'
import type { ProviderConfig } from '@/api/types'

export interface AgentModelPickerProps {
  currentProvider: string
  currentModelId: string
  providers: Readonly<Record<string, ProviderConfig>>
  onChange: (provider: string, modelId: string) => void
  disabled?: boolean
}

export function AgentModelPicker({
  currentProvider,
  currentModelId,
  providers,
  onChange,
  disabled,
}: AgentModelPickerProps) {
  const options = useMemo(() => {
    const opts: SelectOption[] = []
    for (const [providerName, config] of Object.entries(providers)) {
      for (const model of config.models) {
        opts.push({
          value: `${providerName}::${model.id}`,
          label: `${providerName} / ${model.alias ?? model.id}`,
        })
      }
    }
    return opts
  }, [providers])

  const currentValue = currentProvider && currentModelId ? `${currentProvider}::${currentModelId}` : ''

  return (
    <SelectField
      label="Model"
      options={options}
      value={currentValue}
      onChange={(val) => {
        const sepIdx = val.indexOf('::')
        if (sepIdx === -1) return
        const provider = val.slice(0, sepIdx)
        const modelId = val.slice(sepIdx + 2)
        if (provider && modelId) {
          onChange(provider, modelId)
        }
      }}
      disabled={disabled}
      placeholder={options.length === 0 ? 'No models available' : 'Select model...'}
    />
  )
}
