import type { Meta, StoryObj } from '@storybook/react'
import type { SinkInfo } from '@/api/types/settings'
import { SinkCard } from './SinkCard'

const meta: Meta<typeof SinkCard> = {
  title: 'Settings/Sinks/SinkCard',
  component: SinkCard,
  parameters: { layout: 'centered' },
}
export default meta

type Story = StoryObj<typeof SinkCard>

const consoleSink: SinkInfo = {
  identifier: '__console__',
  sink_type: 'console',
  level: 'INFO',
  json_format: false,
  rotation: null,
  is_default: true,
  enabled: true,
  routing_prefixes: [],
}

const fileSink: SinkInfo = {
  identifier: 'synthorg.log',
  sink_type: 'file',
  level: 'INFO',
  json_format: true,
  rotation: { strategy: 'builtin', max_bytes: 10485760, backup_count: 5 },
  is_default: true,
  enabled: true,
  routing_prefixes: [],
}

const customSink: SinkInfo = {
  identifier: 'custom/audit.log',
  sink_type: 'file',
  level: 'WARNING',
  json_format: true,
  rotation: { strategy: 'builtin', max_bytes: 5242880, backup_count: 3 },
  is_default: false,
  enabled: true,
  routing_prefixes: ['synthorg.security', 'synthorg.api'],
}

const disabledSink: SinkInfo = {
  ...fileSink,
  identifier: 'debug.log',
  level: 'DEBUG',
  enabled: false,
}

export const Console: Story = { args: { sink: consoleSink, onEdit: () => {} } }
export const File: Story = { args: { sink: fileSink, onEdit: () => {} } }
export const Custom: Story = { args: { sink: customSink, onEdit: () => {} } }
export const Disabled: Story = { args: { sink: disabledSink, onEdit: () => {} } }
