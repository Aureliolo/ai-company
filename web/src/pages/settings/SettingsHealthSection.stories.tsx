import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import type { SettingNamespace } from '@/api/types/settings'
import { NamespaceTabBar } from './SettingsHealthSection'

const meta: Meta<typeof NamespaceTabBar> = {
  title: 'Settings/NamespaceTabBar',
  component: NamespaceTabBar,
}
export default meta

type Story = StoryObj<typeof NamespaceTabBar>

const namespaces = ['api', 'memory', 'budget', 'security', 'coordination', 'observability', 'backup'] as const
const counts = new Map<string, number>([
  ['api', 7],
  ['memory', 3],
  ['budget', 10],
  ['security', 4],
  ['coordination', 5],
  ['observability', 4],
  ['backup', 7],
])

export const AllActive: Story = {
  render: function Render() {
    const [active, setActive] = useState<SettingNamespace | null>(null)
    return (
      <NamespaceTabBar
        namespaces={namespaces}
        activeNamespace={active}
        onSelect={setActive}
        namespaceCounts={counts}
      />
    )
  },
}

export const NamespaceSelected: Story = {
  args: {
    namespaces,
    activeNamespace: 'budget',
    namespaceCounts: counts,
    onSelect: (ns: string | null) => {
      console.log('Selected namespace:', ns)
    },
  },
}
