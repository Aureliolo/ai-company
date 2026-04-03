import type { Meta, StoryObj } from '@storybook/react-vite'
import { DepartmentCeremonyOverride } from './DepartmentCeremonyOverride'

const meta = {
  title: 'OrgEdit/DepartmentCeremonyOverride',
  component: DepartmentCeremonyOverride,
  tags: ['autodocs'],
} satisfies Meta<typeof DepartmentCeremonyOverride>

export default meta
type Story = StoryObj<typeof meta>

export const Inherit: Story = {
  args: { policy: null, onChange: () => {} },
}

export const Override: Story = {
  args: {
    policy: { strategy: 'calendar', auto_transition: true, transition_threshold: 0.8 },
    onChange: () => {},
  },
}

export const Disabled: Story = {
  args: { policy: null, onChange: () => {}, disabled: true },
}
