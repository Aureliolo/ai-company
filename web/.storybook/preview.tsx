import { definePreview } from '@storybook/react-vite'
import { initialize, mswLoader } from 'msw-storybook-addon'
import '../src/styles/global.css'

// Start the MSW service worker before any stories render.
// 'bypass' lets non-mocked requests (assets, HMR) pass through silently.
initialize({ onUnhandledRequest: 'bypass' })

export default definePreview({
  parameters: {
    a11y: { test: 'error' },
    backgrounds: {
      options: {
        dark: { name: 'SynthOrg Dark', value: '#0a0a12' },
      },
    },
  },
  initialGlobals: {
    backgrounds: { value: 'dark' },
  },
  loaders: [mswLoader],
  decorators: [
    (Story) => (
      <div className="dark bg-background p-4 text-foreground">
        <Story />
      </div>
    ),
  ],
})
