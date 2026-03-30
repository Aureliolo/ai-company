import type { Meta, StoryObj } from '@storybook/react'
import { MobileUnsupportedOverlay } from './mobile-unsupported'

const meta: Meta<typeof MobileUnsupportedOverlay> = {
  title: 'UI/MobileUnsupportedOverlay',
  component: MobileUnsupportedOverlay,
  tags: ['autodocs'],
  parameters: {
    viewport: { defaultViewport: 'mobile1' },
    layout: 'fullscreen',
  },
}

export default meta
type Story = StoryObj<typeof MobileUnsupportedOverlay>

export const Default: Story = {}
