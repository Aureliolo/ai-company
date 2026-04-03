import type { Meta, StoryObj } from '@storybook/react-vite'
import { ModelPullDialog } from './ModelPullDialog'
import { useProvidersStore } from '@/stores/providers'

const meta = {
  title: 'Providers/ModelPullDialog',
  component: ModelPullDialog,
  args: {
    providerName: 'test-provider',
    onClose: () => {},
  },
  decorators: [
    (Story) => {
      useProvidersStore.setState({
        pullingModel: false,
        pullProgress: null,
      })
      return (
        <div className="min-h-[400px]">
          <Story />
        </div>
      )
    },
  ],
} satisfies Meta<typeof ModelPullDialog>

export default meta
type Story = StoryObj<typeof meta>

export const Closed: Story = {
  args: { open: false },
}

export const Open: Story = {
  args: { open: true },
}

export const Pulling: Story = {
  args: { open: true },
  decorators: [
    (Story) => {
      useProvidersStore.setState({
        pullingModel: true,
        pullProgress: {
          status: 'Downloading model layers...',
          progress_percent: 42,
          total_bytes: 4_000_000_000,
          completed_bytes: 1_680_000_000,
          error: null,
          done: false,
        },
      })
      return <Story />
    },
  ],
}

export const PullError: Story = {
  args: { open: true },
  decorators: [
    (Story) => {
      useProvidersStore.setState({
        pullingModel: true,
        pullProgress: {
          status: 'Error',
          progress_percent: 0,
          total_bytes: null,
          completed_bytes: null,
          error: 'Connection refused: unable to reach model registry',
          done: false,
        },
      })
      return <Story />
    },
  ],
}
