import type { Meta, StoryObj } from '@storybook/react'
import { StaggerGroup, StaggerItem } from './stagger-group'

const meta = {
  title: 'Animation/StaggerGroup',
  component: StaggerGroup,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
  },
} satisfies Meta<typeof StaggerGroup>

export default meta
type Story = StoryObj<typeof meta>

function DemoCard({ label }: { label: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <span className="text-sm font-medium text-foreground">{label}</span>
    </div>
  )
}

export const Default: Story = {
  render: () => (
    <StaggerGroup className="grid grid-cols-3 gap-4">
      {Array.from({ length: 6 }, (_, i) => (
        <StaggerItem key={i}>
          <DemoCard label={`Card ${i + 1}`} />
        </StaggerItem>
      ))}
    </StaggerGroup>
  ),
}

export const CustomDelay: Story = {
  render: () => (
    <StaggerGroup className="grid grid-cols-3 gap-4" staggerDelay={0.1}>
      {Array.from({ length: 6 }, (_, i) => (
        <StaggerItem key={i}>
          <DemoCard label={`Card ${i + 1}`} />
        </StaggerItem>
      ))}
    </StaggerGroup>
  ),
}

export const NoAnimation: Story = {
  render: () => (
    <StaggerGroup className="grid grid-cols-3 gap-4" animate={false}>
      {Array.from({ length: 6 }, (_, i) => (
        <StaggerItem key={i}>
          <DemoCard label={`Card ${i + 1}`} />
        </StaggerItem>
      ))}
    </StaggerGroup>
  ),
}

export const WithLayoutAnimation: Story = {
  render: () => (
    <StaggerGroup className="flex flex-col gap-3">
      {['Alpha', 'Beta', 'Gamma', 'Delta'].map((name) => (
        <StaggerItem key={name} layoutId={name} layout>
          <DemoCard label={name} />
        </StaggerItem>
      ))}
    </StaggerGroup>
  ),
}
