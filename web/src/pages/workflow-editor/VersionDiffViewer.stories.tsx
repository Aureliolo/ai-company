import type { Meta, StoryObj } from '@storybook/react-vite'
import { VersionDiffViewer } from './VersionDiffViewer'

const meta = {
  title: 'Pages/WorkflowEditor/VersionDiffViewer',
  component: VersionDiffViewer,
} satisfies Meta<typeof VersionDiffViewer>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}
