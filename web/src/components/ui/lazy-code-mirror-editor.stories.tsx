import type { Meta, StoryObj } from '@storybook/react'
import { LazyCodeMirrorEditor } from './lazy-code-mirror-editor'

const meta: Meta<typeof LazyCodeMirrorEditor> = {
  title: 'UI/LazyCodeMirrorEditor',
  component: LazyCodeMirrorEditor,
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof LazyCodeMirrorEditor>

export const JsonMode: Story = {
  args: {
    value: '{\n  "name": "SynthOrg",\n  "version": "0.5.0"\n}',
    language: 'json',
    readOnly: false,
  },
}

export const YamlMode: Story = {
  args: {
    value: 'company:\n  name: SynthOrg\n  departments:\n    - engineering\n    - design',
    language: 'yaml',
    readOnly: false,
  },
}

export const ReadOnly: Story = {
  args: {
    value: '{\n  "status": "readonly"\n}',
    language: 'json',
    readOnly: true,
  },
}
