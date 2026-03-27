import type { Meta, StoryObj } from '@storybook/react'
import { AgentCreateDialog } from './AgentCreateDialog'

const meta = {
  title: 'OrgEdit/AgentCreateDialog',
  component: AgentCreateDialog,
  args: {
    open: true,
    onOpenChange: () => {},
    departments: [
      { name: 'engineering', display_name: 'Engineering', teams: [] },
      { name: 'product', display_name: 'Product', teams: [] },
    ],
    onCreate: async () => { throw new Error('Not implemented') },
  },
} satisfies Meta<typeof AgentCreateDialog>

export default meta
type Story = StoryObj<typeof meta>

export const Open: Story = {}

export const Closed: Story = {
  args: { open: false },
}
