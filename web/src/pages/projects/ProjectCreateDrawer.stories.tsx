import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { ProjectCreateDrawer } from './ProjectCreateDrawer'
import { Button } from '@/components/ui/button'

const meta = {
  title: 'Pages/Projects/ProjectCreateDrawer',
  component: ProjectCreateDrawer,
  tags: ['autodocs'],
} satisfies Meta<typeof ProjectCreateDrawer>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { open: true, onClose: () => {} },
}

export const Interactive: Story = {
  args: { open: false, onClose: () => {} },
  render: function Render() {
    const [open, setOpen] = useState(false)
    return (
      <>
        <Button onClick={() => setOpen(true)}>Open Drawer</Button>
        <ProjectCreateDrawer open={open} onClose={() => setOpen(false)} />
      </>
    )
  },
}
