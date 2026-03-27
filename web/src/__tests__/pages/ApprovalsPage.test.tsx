import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import ApprovalsPage from '@/pages/ApprovalsPage'
import { makeApproval } from '../helpers/factories'
import type { UseApprovalsDataReturn } from '@/hooks/useApprovalsData'

// Mutable hook return that tests can override
const defaultReturn: UseApprovalsDataReturn = {
  approvals: [],
  selectedApproval: null,
  total: 0,
  loading: false,
  loadingDetail: false,
  error: null,
  wsConnected: true,
  wsSetupError: null,
  fetchApproval: vi.fn(),
  approveOne: vi.fn().mockResolvedValue(undefined),
  rejectOne: vi.fn().mockResolvedValue(undefined),
  optimisticApprove: vi.fn().mockReturnValue(() => {}),
  optimisticReject: vi.fn().mockReturnValue(() => {}),
  selectedIds: new Set(),
  toggleSelection: vi.fn(),
  selectAllInGroup: vi.fn(),
  deselectAllInGroup: vi.fn(),
  clearSelection: vi.fn(),
  batchApprove: vi.fn().mockResolvedValue({ succeeded: 0, failed: 0 }),
  batchReject: vi.fn().mockResolvedValue({ succeeded: 0, failed: 0 }),
}

let hookReturn = { ...defaultReturn }
const getApprovalsData = vi.fn(() => hookReturn)

vi.mock('@/hooks/useApprovalsData', () => {
  const hookName = 'useApprovalsData'
  return { [hookName]: () => getApprovalsData() }
})

function renderPage() {
  return render(
    <MemoryRouter>
      <ApprovalsPage />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  hookReturn = { ...defaultReturn, selectedIds: new Set() }
  vi.clearAllMocks()
})

describe('ApprovalsPage', () => {
  it('renders loading skeleton when loading with no data', () => {
    hookReturn = { ...defaultReturn, loading: true, approvals: [], selectedIds: new Set() }
    renderPage()
    expect(screen.getByLabelText('Loading approvals')).toBeInTheDocument()
  })

  it('renders page heading', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: 'Approvals' })).toBeInTheDocument()
  })

  it('renders error banner when error exists', () => {
    hookReturn = { ...defaultReturn, error: 'Something went wrong', selectedIds: new Set() }
    renderPage()
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
  })

  it('renders WS disconnected banner', () => {
    hookReturn = { ...defaultReturn, wsConnected: false, selectedIds: new Set() }
    renderPage()
    expect(screen.getByText(/real-time updates disconnected/i)).toBeInTheDocument()
  })

  it('renders empty state when no approvals', () => {
    renderPage()
    expect(screen.getByText('No approvals')).toBeInTheDocument()
  })

  it('renders metric cards for risk levels', () => {
    hookReturn = {
      ...defaultReturn,
      approvals: [
        makeApproval('1', { risk_level: 'critical', status: 'pending' }),
        makeApproval('2', { risk_level: 'critical', status: 'pending' }),
        makeApproval('3', { risk_level: 'high', status: 'pending' }),
      ],
      selectedIds: new Set(),
    }
    renderPage()
    expect(screen.getByText('Critical Approvals')).toBeInTheDocument()
    expect(screen.getByText('High Approvals')).toBeInTheDocument()
  })

  it('renders approval cards grouped by risk level', () => {
    hookReturn = {
      ...defaultReturn,
      approvals: [
        makeApproval('1', { risk_level: 'critical', title: 'Deploy prod' }),
        makeApproval('2', { risk_level: 'high', title: 'Push to main' }),
      ],
      selectedIds: new Set(),
    }
    renderPage()
    expect(screen.getByText('Deploy prod')).toBeInTheDocument()
    expect(screen.getByText('Push to main')).toBeInTheDocument()
    expect(screen.getByText('Critical Approvals')).toBeInTheDocument()
    expect(screen.getByText('High Approvals')).toBeInTheDocument()
  })

  it('does not render skeleton when loading with existing data', () => {
    hookReturn = {
      ...defaultReturn,
      loading: true,
      approvals: [makeApproval('1')],
      selectedIds: new Set(),
    }
    renderPage()
    expect(screen.queryByLabelText('Loading approvals')).not.toBeInTheDocument()
  })
})
