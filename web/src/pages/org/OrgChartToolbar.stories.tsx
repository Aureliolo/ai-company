import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { OrgChartToolbar, type ViewMode } from './OrgChartToolbar'

function InteractiveToolbar() {
  const [viewMode, setViewMode] = useState<ViewMode>('hierarchy')
  return (
    <OrgChartToolbar
      viewMode={viewMode}
      onViewModeChange={setViewMode}
      onFitView={() => {}}
      onZoomIn={() => {}}
      onZoomOut={() => {}}
    />
  )
}

const meta = {
  title: 'OrgChart/OrgChartToolbar',
  component: InteractiveToolbar,
  tags: ['autodocs'],
  parameters: {
    a11y: { test: 'error' },
  },
} satisfies Meta<typeof InteractiveToolbar>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}
