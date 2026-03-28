import { useState, useEffect } from 'react'
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
 * The AdminCreation story patches the module export before the
 * component mounts using a Storybook loader + a gate component
 * that waits until the patch is applied.
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
 * Gate component that applies the setup API patch before rendering
 * LoginPage, then restores it on unmount.
 */
function AdminCreationGate() {
  const [ready, setReady] = useState(false)
  const [restore, setRestore] = useState<(() => void) | null>(null)

  useEffect(() => {
    let cancelled = false
    void import('@/api/endpoints/setup').then((mod) => {
      if (cancelled) return
      const original = mod.getSetupStatus
      ;(mod as Record<string, unknown>).getSetupStatus = () =>
        Promise.resolve({
          needs_admin: true,
          needs_setup: true,
          has_providers: false,
          has_name_locales: false,
          has_company: false,
          has_agents: false,
          min_password_length: 12,
        })
      setRestore(() => () => {
        ;(mod as Record<string, unknown>).getSetupStatus = original
      })
      setReady(true)
    })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    return () => { if (restore) restore() }
  }, [restore])

  if (!ready) return null
  return <LoginPage />
}

/**
 * Admin creation form.
 *
 * Uses a gate component that patches getSetupStatus before
 * LoginPage mounts, ensuring needs_admin: true is seen.
 */
export const AdminCreation: Story = {
  render: () => <AdminCreationGate />,
}
