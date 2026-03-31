import type { Meta, StoryObj } from '@storybook/react'
import { FloatingSaveBar } from './FloatingSaveBar'

const meta: Meta<typeof FloatingSaveBar> = {
  title: 'Settings/FloatingSaveBar',
  component: FloatingSaveBar,
}
export default meta

type Story = StoryObj<typeof FloatingSaveBar>

export const SingleChange: Story = {
  args: { dirtyCount: 1, saving: false, onSave: () => {}, onDiscard: () => {}, saveError: null },
}

export const MultipleChanges: Story = {
  args: { dirtyCount: 5, saving: false, onSave: () => {}, onDiscard: () => {}, saveError: null },
}

export const Saving: Story = {
  args: { dirtyCount: 3, saving: true, onSave: () => {}, onDiscard: () => {}, saveError: null },
}

export const WithError: Story = {
  args: { dirtyCount: 2, saving: false, onSave: () => {}, onDiscard: () => {}, saveError: 'Network error: failed to save' },
}

export const Hidden: Story = {
  args: { dirtyCount: 0, saving: false, onSave: () => {}, onDiscard: () => {}, saveError: null },
}
