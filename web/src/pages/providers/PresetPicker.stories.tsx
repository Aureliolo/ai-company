import type { Meta, StoryObj } from '@storybook/react-vite'
import { PresetPicker } from './PresetPicker'
import type { ProviderPreset } from '@/api/types'
import { useState } from 'react'

const samplePresets: ProviderPreset[] = [
  { name: 'anthropic', display_name: 'Anthropic', description: 'Claude models', driver: 'litellm', litellm_provider: 'anthropic', auth_type: 'api_key', supported_auth_types: ['api_key', 'subscription'], default_base_url: null, candidate_urls: [], default_models: [] },
  { name: 'openai', display_name: 'OpenAI', description: 'GPT and o-series', driver: 'litellm', litellm_provider: 'openai', auth_type: 'api_key', supported_auth_types: ['api_key'], default_base_url: null, candidate_urls: [], default_models: [] },
  { name: 'ollama', display_name: 'Ollama', description: 'Local inference', driver: 'litellm', litellm_provider: 'ollama', auth_type: 'none', supported_auth_types: ['none'], default_base_url: 'http://localhost:11434', candidate_urls: [], default_models: [] },
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
  args: { presets: samplePresets, selected: 'anthropic', onSelect: () => {} },
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
