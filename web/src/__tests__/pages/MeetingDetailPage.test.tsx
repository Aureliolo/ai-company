import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import type { UseMeetingDetailDataReturn } from '@/hooks/useMeetingDetailData'
import { makeMeeting } from '../helpers/factories'

const defaultHookReturn: UseMeetingDetailDataReturn = {
  meeting: makeMeeting('meeting-1'),
  loading: false,
  error: null,
  wsConnected: true,
  wsSetupError: null,
}

let hookReturn = { ...defaultHookReturn }

const getDetailData = vi.fn(() => hookReturn)
vi.mock('@/hooks/useMeetingDetailData', () => {
  const hookName = 'useMeetingDetailData'
  return { [hookName]: () => getDetailData() }
})

// Static import after vi.mock
import MeetingDetailPage from '@/pages/MeetingDetailPage'

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={['/meetings/meeting-1']}>
      <Routes>
        <Route path="/meetings/:meetingId" element={<MeetingDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('MeetingDetailPage', () => {
  beforeEach(() => {
    hookReturn = { ...defaultHookReturn }
  })

  it('renders loading skeleton when loading with no data', () => {
    hookReturn = { ...defaultHookReturn, loading: true, meeting: null }
    renderDetail()
    expect(screen.getByLabelText('Loading meeting detail')).toBeInTheDocument()
  })

  it('renders meeting type name as heading', () => {
    renderDetail()
    expect(screen.getByRole('heading', { level: 1, name: 'Daily Standup' })).toBeInTheDocument()
  })

  it('renders agenda section', () => {
    renderDetail()
    expect(screen.getByText('Agenda')).toBeInTheDocument()
    expect(screen.getByText('Status updates')).toBeInTheDocument()
  })

  it('renders contributions section', () => {
    renderDetail()
    expect(screen.getByText('Contributions')).toBeInTheDocument()
    expect(screen.getByText('Completed the API endpoint work.')).toBeInTheDocument()
  })

  it('renders token usage section', () => {
    renderDetail()
    expect(screen.getByText('Token Usage')).toBeInTheDocument()
  })

  it('renders decisions section', () => {
    renderDetail()
    expect(screen.getByText('Decisions')).toBeInTheDocument()
    expect(screen.getByText('Continue current sprint tasks')).toBeInTheDocument()
  })

  it('renders action items section', () => {
    renderDetail()
    expect(screen.getByText('Action Items')).toBeInTheDocument()
    expect(screen.getByText('Finish test coverage')).toBeInTheDocument()
  })

  it('renders summary section', () => {
    renderDetail()
    expect(screen.getByText('Summary')).toBeInTheDocument()
    expect(screen.getByText('Team is on track.')).toBeInTheDocument()
  })

  it('shows error banner when error is set', () => {
    hookReturn = { ...defaultHookReturn, meeting: null, error: 'Meeting not found' }
    renderDetail()
    expect(screen.getByText('Meeting not found')).toBeInTheDocument()
  })

  it('shows in-progress notice when no minutes', () => {
    hookReturn = {
      ...defaultHookReturn,
      meeting: makeMeeting('m-2', { status: 'in_progress', minutes: null }),
    }
    renderDetail()
    expect(screen.getByText('Meeting In Progress')).toBeInTheDocument()
  })

  it('shows error message from meeting', () => {
    hookReturn = {
      ...defaultHookReturn,
      meeting: makeMeeting('m-3', { status: 'failed', error_message: 'Token budget exceeded' }),
    }
    renderDetail()
    expect(screen.getByText('Token budget exceeded')).toBeInTheDocument()
  })

  it('renders back navigation link', () => {
    renderDetail()
    expect(screen.getByLabelText('Back to meetings')).toBeInTheDocument()
  })

  it('shows wsSetupError when provided', () => {
    hookReturn = { ...defaultHookReturn, wsConnected: false, wsSetupError: 'WS auth failed' }
    renderDetail()
    expect(screen.getByText('WS auth failed')).toBeInTheDocument()
  })
})
