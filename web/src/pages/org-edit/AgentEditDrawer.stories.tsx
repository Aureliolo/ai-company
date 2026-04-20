import type { Meta, StoryObj } from '@storybook/react'
import { AgentEditDrawer } from './AgentEditDrawer'
import type { AgentConfig } from '@/api/types/agents'
import type { Department } from '@/api/types/org'

const mockAgent: AgentConfig = {
  id: 'agent-alice',
  name: 'alice',
  role: 'Lead Developer',
  department: 'engineering',
  level: 'lead',
  status: 'active',
  personality: {
    traits: ['analytical'], communication_style: 'direct',
    risk_tolerance: 'medium', creativity: 'medium', description: 'Test',
    openness: 0.7, conscientiousness: 0.8, extraversion: 0.5,
    agreeableness: 0.6, stress_response: 0.5, decision_making: 'analytical',
    collaboration: 'team', verbosity: 'balanced', conflict_approach: 'collaborate',
  },
  model: { provider: 'test-provider', model_id: 'test-medium-001', temperature: 0.7, max_tokens: 4096, fallback_model: null },
  memory: { type: 'persistent', retention_days: null },
  tools: { access_level: 'standard', allowed: ['code_edit'], denied: [] },
  authority: {},
  autonomy_level: 'semi',
  hiring_date: '2026-03-01T00:00:00Z',
}

const mockDepartments: Department[] = [
  { name: 'engineering', display_name: 'Engineering', teams: [] },
  { name: 'product', display_name: 'Product', teams: [] },
]

const meta = {
  title: 'OrgEdit/AgentEditDrawer',
  component: AgentEditDrawer,
  parameters: {
    a11y: { test: 'error' },
  },
  args: {
    open: true,
    onClose: () => {},
    agent: mockAgent,
    departments: mockDepartments,
    onUpdate: async () => mockAgent,
    onDelete: async () => {},
    saving: false,
  },
} satisfies Meta<typeof AgentEditDrawer>

export default meta
type Story = StoryObj<typeof meta>

export const Open: Story = {}

export const Closed: Story = {
  args: { open: false },
}

export const Saving: Story = {
  args: { saving: true },
}
