import type { Meta, StoryObj } from '@storybook/react-vite'
import { VersionHistoryPanel } from './VersionHistoryPanel'

const meta = {
  title: 'Pages/WorkflowEditor/VersionHistoryPanel',
  component: VersionHistoryPanel,
  args: {
    open: true,
    onClose: () => {},
  },
  parameters: {
    a11y: { test: 'error' },
  },
} satisfies Meta<typeof VersionHistoryPanel>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}

export const Closed: Story = {
  args: {
    open: false,
  },
}
