import type { Meta, StoryObj } from '@storybook/react-vite'
import { TestConnectionResult } from './TestConnectionResult'

const meta = {
  title: 'Providers/TestConnectionResult',
  component: TestConnectionResult,
  tags: ['autodocs'],
  decorators: [(Story) => <div className="max-w-md"><Story /></div>],
} satisfies Meta<typeof TestConnectionResult>

export default meta
type Story = StoryObj<typeof meta>

export const Success: Story = {
  args: { result: { success: true, latency_ms: 245, error: null, model_tested: 'claude-sonnet-4-20250514' } },
}

export const Failure: Story = {
  args: { result: { success: false, latency_ms: null, error: 'Connection refused: ECONNREFUSED', model_tested: null } },
}

export const SuccessNoModel: Story = {
  args: { result: { success: true, latency_ms: 89, error: null, model_tested: null } },
}
