import type { Meta, StoryObj } from '@storybook/react'
import { GeneralTab } from './GeneralTab'
import type { CompanyConfig } from '@/api/types/org'

const mockConfig: CompanyConfig = {
  company_name: 'Acme Corp',
  agents: [],
  departments: [
    { name: 'engineering', display_name: 'Engineering', teams: [] },
  ],
}

const meta = {
  title: 'OrgEdit/GeneralTab',
  component: GeneralTab,
  parameters: {
    a11y: { test: 'error' },
  },
  args: {
    config: mockConfig,
    onUpdate: async () => {},
    saving: false,
  },
} satisfies Meta<typeof GeneralTab>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}

export const EmptyConfig: Story = {
  args: { config: null },
}

export const Saving: Story = {
  args: { saving: true },
}
