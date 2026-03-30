import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { NamespaceTabBar } from '@/pages/settings/SettingsHealthSection'

describe('NamespaceTabBar', () => {
  const namespaces = ['api', 'memory', 'budget'] as const
  const counts = new Map<string, number>([
    ['api', 5],
    ['memory', 3],
    ['budget', 4],
  ])

  it('renders All tab and namespace tabs', () => {
    render(
      <NamespaceTabBar
        namespaces={namespaces}
        activeNamespace={null}
        onSelect={() => {}}
        namespaceCounts={counts}
      />,
    )
    expect(screen.getByText('All')).toBeInTheDocument()
    expect(screen.getByText('Server')).toBeInTheDocument()
    expect(screen.getByText('Memory')).toBeInTheDocument()
    expect(screen.getByText('Budget')).toBeInTheDocument()
  })

  it('highlights All tab when activeNamespace is null', () => {
    render(
      <NamespaceTabBar
        namespaces={namespaces}
        activeNamespace={null}
        onSelect={() => {}}
        namespaceCounts={counts}
      />,
    )
    expect(screen.getByText('All').closest('button')).toHaveAttribute('aria-selected', 'true')
  })

  it('highlights active namespace tab', () => {
    render(
      <NamespaceTabBar
        namespaces={namespaces}
        activeNamespace="memory"
        onSelect={() => {}}
        namespaceCounts={counts}
      />,
    )
    expect(screen.getByText('Memory').closest('button')).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByText('All').closest('button')).toHaveAttribute('aria-selected', 'false')
  })

  it('calls onSelect when a tab is clicked', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    render(
      <NamespaceTabBar
        namespaces={namespaces}
        activeNamespace={null}
        onSelect={onSelect}
        namespaceCounts={counts}
      />,
    )
    await user.click(screen.getByText('Budget'))
    expect(onSelect).toHaveBeenCalledWith('budget')
  })

  it('calls onSelect(null) when All tab is clicked', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    render(
      <NamespaceTabBar
        namespaces={namespaces}
        activeNamespace="api"
        onSelect={onSelect}
        namespaceCounts={counts}
      />,
    )
    await user.click(screen.getByText('All'))
    expect(onSelect).toHaveBeenCalledWith(null)
  })

  it('hides namespaces with 0 count', () => {
    const zeroCounts = new Map<string, number>([
      ['api', 5],
      ['memory', 0],
      ['budget', 4],
    ])
    render(
      <NamespaceTabBar
        namespaces={namespaces}
        activeNamespace={null}
        onSelect={() => {}}
        namespaceCounts={zeroCounts}
      />,
    )
    expect(screen.queryByText('Memory')).not.toBeInTheDocument()
  })

  it('shows setting count next to each tab', () => {
    render(
      <NamespaceTabBar
        namespaces={namespaces}
        activeNamespace={null}
        onSelect={() => {}}
        namespaceCounts={counts}
      />,
    )
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
  })
})
