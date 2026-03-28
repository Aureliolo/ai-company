import { useEffect } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { MemoryRouter } from 'react-router'
import LoginPage from './LoginPage'

/**
 * LoginPage stories.
 *
 * The component calls `getSetupStatus()` on mount.  In Storybook there
 * is no backend, so the call rejects and the page falls back to the
 * Sign In form (the default behaviour for network errors).
 *
 * The AdminCreation story works around this by rendering a wrapper
 * that patches the module before the component mounts.
 */
const meta = {
  title: 'Pages/Login',
  component: LoginPage,
  parameters: { layout: 'fullscreen' },
  decorators: [
    (Story) => (
      <MemoryRouter>
        <Story />
      </MemoryRouter>
    ),
  ],
} satisfies Meta<typeof LoginPage>

export default meta
type Story = StoryObj<typeof meta>

/** Default login form (no backend -- falls back to Sign In). */
export const DefaultLogin: Story = {}

/**
 * Admin creation form.
 *
 * We patch the setup API module before rendering so the component
 * sees `needs_admin: true` from the status check.
 */
export const AdminCreation: Story = {
  loaders: [
    async () => {
      const setupApi = await import('@/api/endpoints/setup')
      const original = setupApi.getSetupStatus
      ;(setupApi as Record<string, unknown>).getSetupStatus = () =>
        Promise.resolve({
          needs_admin: true,
          needs_setup: true,
          has_providers: false,
          has_name_locales: false,
          has_company: false,
          has_agents: false,
          min_password_length: 12,
        })
      return { restoreSetup: () => { (setupApi as Record<string, unknown>).getSetupStatus = original } }
    },
  ],
  decorators: [
    (Story, context) => {
      const restore = (context.loaded as { restoreSetup?: () => void })?.restoreSetup
      // Restore on unmount via useEffect cleanup instead of setTimeout.
      useEffect(() => {
        return () => { if (restore) restore() }
      }, [restore])
      return (
        <MemoryRouter>
          <Story />
        </MemoryRouter>
      )
    },
  ],
}
