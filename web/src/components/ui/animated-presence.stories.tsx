import type { Meta, StoryObj } from '@storybook/react'
import { useState } from 'react'
import { AnimatedPresence } from './animated-presence'

const meta = {
  title: 'Animation/AnimatedPresence',
  component: AnimatedPresence,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
} satisfies Meta<typeof AnimatedPresence>

export default meta
type Story = StoryObj<typeof meta>

function PageContent({ label, color }: { label: string; color: string }) {
  return (
    <div
      className={`flex h-48 items-center justify-center rounded-lg border border-border ${color}`}
    >
      <span className="text-lg font-semibold text-foreground">{label}</span>
    </div>
  )
}

function TransitionDemo() {
  const pages = [
    { key: '/dashboard', label: 'Dashboard', color: 'bg-card' },
    { key: '/agents', label: 'Agents', color: 'bg-surface' },
    { key: '/tasks', label: 'Tasks', color: 'bg-card' },
  ]
  const [index, setIndex] = useState(0)
  const current = pages[index] ?? pages[0]

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {pages.map((page, i) => (
          <button
            key={page.key}
            onClick={() => setIndex(i)}
            className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
              i === index
                ? 'bg-accent text-accent-foreground'
                : 'bg-card text-foreground hover:bg-card-hover'
            }`}
          >
            {page.label}
          </button>
        ))}
      </div>
      <AnimatedPresence routeKey={current!.key}>
        <PageContent label={current!.label} color={current!.color} />
      </AnimatedPresence>
    </div>
  )
}

export const Default: Story = {
  args: { routeKey: '/', children: null },
  render: () => <TransitionDemo />,
}
