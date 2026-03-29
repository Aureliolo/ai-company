import { render, screen } from '@testing-library/react'
import { DepartmentsTab, type DepartmentsTabProps } from '@/pages/org-edit/DepartmentsTab'
import { makeCompanyConfig, makeDepartmentHealth } from '../../helpers/factories'

const noopAsync = vi.fn().mockResolvedValue(undefined)
const noopRollback = vi.fn().mockReturnValue(() => {})

function renderTab(overrides?: Partial<DepartmentsTabProps>) {
  const props: DepartmentsTabProps = {
    config: makeCompanyConfig(),
    departmentHealths: [
      makeDepartmentHealth('engineering'),
      makeDepartmentHealth('product', { utilization_percent: 72, agent_count: 1 }),
    ],
    saving: false,
    onCreateDepartment: noopAsync,
    onUpdateDepartment: noopAsync,
    onDeleteDepartment: noopAsync,
    onReorderDepartments: noopAsync,
    optimisticReorderDepartments: noopRollback,
    ...overrides,
  }
  return render(<DepartmentsTab {...props} />)
}

describe('DepartmentsTab', () => {
  beforeEach(() => vi.resetAllMocks())

  it('renders empty state when config has no departments', () => {
    renderTab({ config: { ...makeCompanyConfig(), departments: [] } })
    expect(screen.getByText('No departments')).toBeInTheDocument()
  })

  it('renders Add Department button', () => {
    renderTab()
    expect(screen.getByText('Add Department')).toBeInTheDocument()
  })

  it('renders department cards', () => {
    renderTab()
    // Each dept name appears in both SectionCard title and DeptHealthBar
    expect(screen.getAllByText('Engineering').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Product').length).toBeGreaterThanOrEqual(1)
  })

  it('renders health bars for departments', () => {
    renderTab()
    // DeptHealthBar uses role="meter"
    const meters = screen.getAllByRole('meter')
    expect(meters.length).toBeGreaterThanOrEqual(2)
  })

  it('renders empty state when config is null', () => {
    renderTab({ config: null })
    expect(screen.getByText('No departments')).toBeInTheDocument()
  })
})
