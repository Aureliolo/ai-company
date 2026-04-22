import type { Meta, StoryObj } from '@storybook/react'
import { useState } from 'react'
import { AnimatedPresence } from './animated-presence'
import { Button } from './button'

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
          <Button
            key={page.key}
            size="sm"
            variant={i === index ? 'default' : 'outline'}
            onClick={() => setIndex(i)}
          >
            {page.label}
          </Button>
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

function StaticContent() {
  return (
    <AnimatedPresence routeKey="/static">
      <PageContent label="Static" color="bg-card" />
    </AnimatedPresence>
  )
}

export const StaticRoute: Story = {
  args: { routeKey: '/static', children: null },
  render: () => <StaticContent />,
}

function ReducedMotionDemo() {
  const [index, setIndex] = useState(0)
  const pages = [
    { key: '/a', label: 'Route A', color: 'bg-card' },
    { key: '/b', label: 'Route B', color: 'bg-surface' },
  ]
  const current = pages[index] ?? pages[0]!
  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        Motion obeys <code>prefers-reduced-motion</code>. Toggle the OS setting (or emulate in devtools) to see the difference between the slide transitions and the reduced-motion fallback.
      </p>
      <Button size="sm" onClick={() => setIndex((i) => (i + 1) % pages.length)}>
        Toggle route
      </Button>
      <AnimatedPresence routeKey={current.key}>
        <PageContent label={current.label} color={current.color} />
      </AnimatedPresence>
    </div>
  )
}

export const ReducedMotion: Story = {
  args: { routeKey: '/', children: null },
  render: () => <ReducedMotionDemo />,
  parameters: {
    a11y: {
      config: {
        rules: [{ id: 'meta-viewport', enabled: false }],
      },
    },
  },
}

function RapidNavigationDemo() {
  const pages = ['/a', '/b', '/c', '/d']
  const [index, setIndex] = useState(0)
  const current = pages[index % pages.length] ?? pages[0]!
  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Button size="sm" onClick={() => setIndex((i) => i + 1)}>
          Next route (simulate rapid nav)
        </Button>
      </div>
      <AnimatedPresence routeKey={current}>
        <PageContent label={`Route ${current}`} color="bg-card" />
      </AnimatedPresence>
    </div>
  )
}

export const RapidNavigation: Story = {
  args: { routeKey: '/', children: null },
  render: () => <RapidNavigationDemo />,
}
