import { render, screen, fireEvent } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import fc from 'fast-check'
import { NodeContextMenu } from '@/pages/org/NodeContextMenu'

describe('NodeContextMenu', () => {
  let baseProps: {
    nodeId: string
    nodeType: 'agent' | 'ceo' | 'department'
    position: { x: number; y: number }
    onClose: () => void
  }

  beforeEach(() => {
    baseProps = {
      nodeId: 'agent-1',
      nodeType: 'agent' as const,
      position: { x: 100, y: 100 },
      onClose: vi.fn(),
    }
  })

  it('renders menu for agent node', () => {
    render(<NodeContextMenu {...baseProps} />)
    expect(screen.getByTestId('node-context-menu')).toBeInTheDocument()
    expect(screen.getByText('View Details')).toBeInTheDocument()
    expect(screen.getByText('Edit Agent')).toBeInTheDocument()
    expect(screen.getByText('Assign to Department')).toBeInTheDocument()
    expect(screen.getByText('Remove Agent')).toBeInTheDocument()
  })

  it('renders menu for department node', () => {
    render(<NodeContextMenu {...baseProps} nodeType="department" />)
    expect(screen.getByText('Edit Department')).toBeInTheDocument()
    expect(screen.getByText('Add Agent')).toBeInTheDocument()
    expect(screen.getByText('Delete Department')).toBeInTheDocument()
  })

  it('calls onViewDetails when clicking View Details', () => {
    const handler = vi.fn()
    render(<NodeContextMenu {...baseProps} onViewDetails={handler} />)
    fireEvent.click(screen.getByText('View Details'))
    expect(handler).toHaveBeenCalledWith('agent-1')
  })

  it('calls onDelete when clicking Remove Agent', () => {
    const handler = vi.fn()
    render(<NodeContextMenu {...baseProps} onDelete={handler} />)
    fireEvent.click(screen.getByText('Remove Agent'))
    expect(handler).toHaveBeenCalledWith('agent-1')
  })

  it('closes on Escape', () => {
    const onClose = vi.fn()
    render(<NodeContextMenu {...baseProps} onClose={onClose} />)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('closes on outside click', () => {
    const onClose = vi.fn()
    render(<NodeContextMenu {...baseProps} onClose={onClose} />)
    fireEvent.mouseDown(document.body)
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('has role="menu"', () => {
    render(<NodeContextMenu {...baseProps} />)
    expect(screen.getByRole('menu')).toBeInTheDocument()
  })

  it('menu items have role="menuitem"', () => {
    render(<NodeContextMenu {...baseProps} />)
    const items = screen.getAllByRole('menuitem')
    expect(items).toHaveLength(4)
  })

  it.each(['agent', 'ceo', 'department'] as const)(
    'renders menu with role="menu" for %s node type',
    (nodeType) => {
      render(<NodeContextMenu {...baseProps} nodeType={nodeType} />)
      expect(screen.getByRole('menu')).toBeInTheDocument()
      const items = screen.getAllByRole('menuitem')
      expect(items.length).toBeGreaterThan(0)
    },
  )

  it('properties: all supported node types render valid menu structures', () => {
    const nodeTypeArb = fc.constantFrom('agent' as const, 'ceo' as const, 'department' as const)
    fc.assert(
      fc.property(nodeTypeArb, (nodeType) => {
        const { unmount } = render(
          <NodeContextMenu {...baseProps} nodeType={nodeType} />,
        )
        const menu = screen.getByRole('menu')
        expect(menu).toBeInTheDocument()
        const items = screen.getAllByRole('menuitem')
        expect(items.length).toBeGreaterThan(0)
        // All items should have type="button"
        for (const item of items) {
          expect(item).toHaveAttribute('type', 'button')
        }
        unmount()
      }),
    )
  })
})
