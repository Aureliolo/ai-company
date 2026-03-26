import type { Meta, StoryObj } from '@storybook/react'
import { useState } from 'react'
import { Button } from './button'
import { ErrorBoundary } from './error-boundary'

const meta = {
  title: 'Feedback/ErrorBoundary',
  component: ErrorBoundary,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
} satisfies Meta<typeof ErrorBoundary>

export default meta
type Story = StoryObj<typeof meta>

function BrokenComponent(): React.ReactNode {
  throw new Error('Something unexpected happened')
}

export const Healthy: Story = {
  args: { children: null },
  render: () => (
    <ErrorBoundary level="section">
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm text-foreground">
          This content renders normally when no error occurs.
        </p>
      </div>
    </ErrorBoundary>
  ),
}

export const PageLevel: Story = {
  args: { children: null },
  render: () => (
    <div className="h-96 border border-dashed border-border rounded-lg">
      <ErrorBoundary level="page">
        <BrokenComponent />
      </ErrorBoundary>
    </div>
  ),
}

export const SectionLevel: Story = {
  args: { children: null },
  render: () => (
    <ErrorBoundary level="section">
      <BrokenComponent />
    </ErrorBoundary>
  ),
}

export const ComponentLevel: Story = {
  args: { children: null },
  render: () => (
    <ErrorBoundary level="component">
      <BrokenComponent />
    </ErrorBoundary>
  ),
}

export const CustomFallback: Story = {
  args: { children: null },
  render: () => (
    <ErrorBoundary
      fallback={({ error, resetErrorBoundary }) => (
        <div className="rounded-lg border border-danger bg-card p-4">
          <p className="text-sm text-danger">Custom fallback: {error.message}</p>
          <Button
            variant="outline"
            size="sm"
            onClick={resetErrorBoundary}
            className="mt-2"
          >
            Reset
          </Button>
        </div>
      )}
    >
      <BrokenComponent />
    </ErrorBoundary>
  ),
}

function MaybeBroken({ broken, onBreak }: { broken: boolean; onBreak: () => void }) {
  if (broken) throw new Error('User triggered this error')
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="text-sm text-foreground">Everything is working fine.</p>
      <Button
        variant="outline"
        size="sm"
        onClick={onBreak}
        className="mt-2"
      >
        Break it
      </Button>
    </div>
  )
}

function InteractiveDemo() {
  const [broken, setBroken] = useState(false)

  return (
    <ErrorBoundary
      level="section"
      onReset={() => setBroken(false)}
    >
      <MaybeBroken broken={broken} onBreak={() => setBroken(true)} />
    </ErrorBoundary>
  )
}

export const Interactive: Story = {
  args: { children: null },
  render: () => <InteractiveDemo />,
}
