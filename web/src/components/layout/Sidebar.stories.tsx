import type { Meta, StoryObj } from '@storybook/react'
import { MemoryRouter } from 'react-router'
import { useAuthStore } from '@/stores/auth'
import { Sidebar } from './Sidebar'

const meta = {
  title: 'Layout/Sidebar',
  component: Sidebar,
  decorators: [
    (Story) => {
      // Set up auth state for user display
      useAuthStore.setState({
        token: 'mock-token',
        user: {
          id: '1',
          username: 'admin',
          role: 'ceo',
          must_change_password: false,
        },
      })
      return (
        <MemoryRouter initialEntries={['/']}>
          <div className="h-screen">
            <Story />
          </div>
        </MemoryRouter>
      )
    },
  ],
  parameters: {
    layout: 'fullscreen',
  },
} satisfies Meta<typeof Sidebar>

export default meta
type Story = StoryObj<typeof meta>

export const Expanded: Story = {
  play: () => {
    localStorage.setItem('sidebar_collapsed', 'false')
  },
}

export const Collapsed: Story = {
  play: () => {
    localStorage.setItem('sidebar_collapsed', 'true')
  },
  decorators: [
    (Story) => {
      localStorage.setItem('sidebar_collapsed', 'true')
      return <Story />
    },
  ],
}
