import { screen } from '@testing-library/react'
import * as fc from 'fast-check'
import { Users } from 'lucide-react'
import { SidebarNavItem } from '@/components/layout/SidebarNavItem'
import { renderWithRouter } from '../../test-utils'

describe('SidebarNavItem', () => {
  it('renders label and icon when expanded', () => {
    renderWithRouter(
      <SidebarNavItem to="/agents" icon={Users} label="Agents" collapsed={false} />,
    )

    expect(screen.getByText('Agents')).toBeInTheDocument()
  })

  it('hides label when collapsed and shows title tooltip', () => {
    renderWithRouter(
      <SidebarNavItem to="/agents" icon={Users} label="Agents" collapsed />,
    )

    expect(screen.queryByText('Agents')).not.toBeInTheDocument()
    expect(screen.getByTitle('Agents')).toBeInTheDocument()
  })

  it('renders badge when count is greater than 0', () => {
    renderWithRouter(
      <SidebarNavItem to="/approvals" icon={Users} label="Approvals" collapsed={false} badge={5} />,
    )

    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('caps badge at 99+', () => {
    renderWithRouter(
      <SidebarNavItem to="/approvals" icon={Users} label="Approvals" collapsed={false} badge={150} />,
    )

    expect(screen.getByText('99+')).toBeInTheDocument()
  })

  it('hides badge when count is 0', () => {
    renderWithRouter(
      <SidebarNavItem to="/approvals" icon={Users} label="Approvals" collapsed={false} badge={0} />,
    )

    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('hides badge when collapsed', () => {
    renderWithRouter(
      <SidebarNavItem to="/approvals" icon={Users} label="Approvals" collapsed badge={5} />,
    )

    expect(screen.queryByText('5')).not.toBeInTheDocument()
  })

  it('renders dot indicator when dotColor is provided', () => {
    renderWithRouter(
      <SidebarNavItem to="/agents" icon={Users} label="Agents" collapsed={false} dotColor="bg-success" />,
    )

    expect(screen.getByText('Agents')).toBeInTheDocument()
    // The dot is rendered as a decorative span with the given color class
    const dot = document.querySelector('.bg-success.rounded-full')
    expect(dot).toBeInTheDocument()
  })

  it('does not render dot indicator when dotColor is not provided', () => {
    renderWithRouter(
      <SidebarNavItem to="/agents" icon={Users} label="Agents" collapsed={false} />,
    )

    const dot = document.querySelector('.rounded-full.size-2')
    expect(dot).not.toBeInTheDocument()
  })

  it('caps badge display at 99+ for any count > 99 (property)', () => {
    fc.assert(
      fc.property(fc.integer({ min: 100, max: 10000 }), (count) => {
        const { unmount } = renderWithRouter(
          <SidebarNavItem to="/test" icon={Users} label="Test" collapsed={false} badge={count} />,
        )
        expect(screen.getByText('99+')).toBeInTheDocument()
        unmount()
      }),
    )
  })

  it('displays exact count for badge values 1-99 (property)', () => {
    fc.assert(
      fc.property(fc.integer({ min: 1, max: 99 }), (count) => {
        const { unmount } = renderWithRouter(
          <SidebarNavItem to="/test" icon={Users} label="Test" collapsed={false} badge={count} />,
        )
        expect(screen.getByText(String(count))).toBeInTheDocument()
        unmount()
      }),
    )
  })
})
