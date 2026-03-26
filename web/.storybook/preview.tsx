import { definePreview } from '@storybook/react-vite'
import '../src/styles/global.css'

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
  decorators: [
    (Story) => (
      <div className="dark bg-background p-4 text-foreground">
        <Story />
      </div>
    ),
  ],
})
