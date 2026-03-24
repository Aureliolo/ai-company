import { screen } from '@testing-library/react'
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
})
