import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { OrgChartToolbar } from '@/pages/org/OrgChartToolbar'

describe('OrgChartToolbar', () => {
  const defaultProps = {
    viewMode: 'hierarchy' as const,
    onViewModeChange: vi.fn(),
    onFitView: vi.fn(),
    onZoomIn: vi.fn(),
    onZoomOut: vi.fn(),
  }

  it('renders toolbar', () => {
    render(<OrgChartToolbar {...defaultProps} />)
    expect(screen.getByTestId('org-chart-toolbar')).toBeInTheDocument()
  })

  it('renders view mode toggle buttons', () => {
    render(<OrgChartToolbar {...defaultProps} />)
    expect(screen.getByText('Hierarchy')).toBeInTheDocument()
    expect(screen.getByText('Communication')).toBeInTheDocument()
  })

  it('calls onViewModeChange when clicking communication', () => {
    const handler = vi.fn()
    render(<OrgChartToolbar {...defaultProps} onViewModeChange={handler} />)
    fireEvent.click(screen.getByText('Communication'))
    expect(handler).toHaveBeenCalledWith('force')
  })

  it('calls onFitView when clicking fit button', () => {
    const handler = vi.fn()
    render(<OrgChartToolbar {...defaultProps} onFitView={handler} />)
    fireEvent.click(screen.getByLabelText('Fit to view'))
    expect(handler).toHaveBeenCalledOnce()
  })

  it('calls onZoomIn when clicking zoom in button', () => {
    const handler = vi.fn()
    render(<OrgChartToolbar {...defaultProps} onZoomIn={handler} />)
    fireEvent.click(screen.getByLabelText('Zoom in'))
    expect(handler).toHaveBeenCalledOnce()
  })

  it('calls onZoomOut when clicking zoom out button', () => {
    const handler = vi.fn()
    render(<OrgChartToolbar {...defaultProps} onZoomOut={handler} />)
    fireEvent.click(screen.getByLabelText('Zoom out'))
    expect(handler).toHaveBeenCalledOnce()
  })
})
