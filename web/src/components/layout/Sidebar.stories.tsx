import type { Meta, StoryObj } from '@storybook/react'
import { MemoryRouter } from 'react-router'
import { useAuthStore } from '@/stores/auth'
import { Sidebar, STORAGE_KEY } from './Sidebar'

const meta = {
  title: 'Layout/Sidebar',
  component: Sidebar,
  decorators: [
    (Story) => {
      // Set up auth state for user display
      useAuthStore.setState({
        authStatus: 'authenticated',
        user: {
          id: '1',
          username: 'admin',
          role: 'ceo',
          must_change_password: false,
          org_roles: ['owner'],
          scoped_departments: [],
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
  decorators: [
    (Story) => {
      localStorage.setItem(STORAGE_KEY, 'false')
      return <Story />
    },
  ],
}

export const Collapsed: Story = {
  decorators: [
    (Story) => {
      localStorage.setItem(STORAGE_KEY, 'true')
      return <Story />
    },
  ],
}
