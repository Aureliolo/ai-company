import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { cn } from '@/lib/utils'
import { CodeMirrorEditor } from './code-mirror-editor'

const SAMPLE_JSON = JSON.stringify(
  {
    api: { server_port: '3001', rate_limit_max_requests: '100' },
    budget: { total_monthly: '100.0', currency: 'EUR' },
  },
  null,
  2,
)

const SAMPLE_YAML = `api:
  server_port: '3001'
  rate_limit_max_requests: '100'
budget:
  total_monthly: '100.0'
  currency: EUR
`

const meta = {
  title: 'UI/CodeMirrorEditor',
  component: CodeMirrorEditor,
  tags: ['autodocs'],
  parameters: { layout: 'padded' },
  argTypes: {
    language: { control: 'select', options: ['json', 'yaml'] },
    readOnly: { control: 'boolean' },
  },
} satisfies Meta<typeof CodeMirrorEditor>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    value: SAMPLE_JSON,
    language: 'json',
    onChange: () => {},
    'aria-label': 'JSON editor',
  },
}

export const YAML: Story = {
  args: {
    value: SAMPLE_YAML,
    language: 'yaml',
    onChange: () => {},
    'aria-label': 'YAML editor',
  },
}

export const ReadOnly: Story = {
  args: {
    value: SAMPLE_JSON,
    language: 'json',
    readOnly: true,
    onChange: () => {},
    'aria-label': 'Read-only JSON editor',
  },
}

export const Empty: Story = {
  args: {
    value: '',
    language: 'json',
    onChange: () => {},
    'aria-label': 'Empty editor',
  },
}

// Note: CodeMirrorEditor has no hover, loading, or error states.
// It is a text editor -- hover styling is handled by CodeMirror's internal
// focus/cursor management. Loading is not applicable (editor renders
// synchronously). Parse errors are displayed externally by the parent
// (e.g. CodeEditorPanel) -- the editor itself renders text as-is.

export const Interactive: Story = {
  args: {
    value: SAMPLE_JSON,
    language: 'json',
    onChange: () => {},
    'aria-label': 'Interactive editor',
  },
  render: function InteractiveEditor() {
    const [value, setValue] = useState(SAMPLE_JSON)
    const [lang, setLang] = useState<'json' | 'yaml'>('json')
    return (
      <div className="space-y-3">
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setLang('json')}
            className={cn(
              'rounded px-2 py-1 text-xs font-medium',
              lang === 'json' ? 'bg-accent/10 text-accent' : 'text-text-muted',
            )}
          >
            JSON
          </button>
          <button
            type="button"
            onClick={() => setLang('yaml')}
            className={cn(
              'rounded px-2 py-1 text-xs font-medium',
              lang === 'yaml' ? 'bg-accent/10 text-accent' : 'text-text-muted',
            )}
          >
            YAML
          </button>
        </div>
        <CodeMirrorEditor
          value={value}
          onChange={setValue}
          language={lang}
          aria-label={`${lang.toUpperCase()} editor`}
        />
        <p className="text-xs text-text-secondary">
          Characters: {value.length}
        </p>
      </div>
    )
  },
}
