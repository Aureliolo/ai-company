import type { Meta, StoryObj } from '@storybook/react-vite'
import { PresetPicker } from './PresetPicker'
import type { ProviderPreset } from '@/api/types/providers'
import { useState } from 'react'

const samplePresets: ProviderPreset[] = [
  { name: 'example-cloud', display_name: 'Example Cloud', description: 'Cloud-hosted models', driver: 'litellm', litellm_provider: 'example-cloud', auth_type: 'api_key', supported_auth_types: ['api_key', 'subscription'], default_base_url: null, requires_base_url: false, candidate_urls: [], default_models: [], supports_model_pull: false, supports_model_delete: false, supports_model_config: false },
  { name: 'example-provider', display_name: 'Example Provider', description: 'Large and medium models', driver: 'litellm', litellm_provider: 'example-provider', auth_type: 'api_key', supported_auth_types: ['api_key'], default_base_url: null, requires_base_url: false, candidate_urls: [], default_models: [], supports_model_pull: false, supports_model_delete: false, supports_model_config: false },
  { name: 'example-local', display_name: 'Example Local', description: 'Local inference', driver: 'litellm', litellm_provider: 'example-local', auth_type: 'none', supported_auth_types: ['none'], default_base_url: 'http://localhost:11434', requires_base_url: true, candidate_urls: [], default_models: [], supports_model_pull: true, supports_model_delete: true, supports_model_config: true },
]

const meta = {
  title: 'Providers/PresetPicker',
  component: PresetPicker,
  tags: ['autodocs'],
  decorators: [(Story) => <div className="max-w-lg"><Story /></div>],
} satisfies Meta<typeof PresetPicker>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { presets: samplePresets, selected: null, onSelect: () => {} },
}

export const WithSelection: Story = {
  args: { presets: samplePresets, selected: 'example-cloud', onSelect: () => {} },
}

export const Loading: Story = {
  args: { presets: [], selected: null, onSelect: () => {}, loading: true },
}

function InteractivePresetPicker() {
  const [selected, setSelected] = useState<string | null>(null)
  return <PresetPicker presets={samplePresets} selected={selected} onSelect={setSelected} />
}

export const Interactive: Story = {
  args: { presets: samplePresets, selected: null, onSelect: () => {} },
  render: () => <InteractivePresetPicker />,
}
