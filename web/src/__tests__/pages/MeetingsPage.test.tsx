import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import type { UseMeetingsDataReturn } from '@/hooks/useMeetingsData'
import { makeMeeting } from '../helpers/factories'

const defaultHookReturn: UseMeetingsDataReturn = {
  meetings: [
    makeMeeting('1', { status: 'completed', meeting_type_name: 'daily_standup' }),
    makeMeeting('2', { status: 'in_progress', meeting_type_name: 'sprint_planning' }),
  ],
  total: 2,
  loading: false,
  error: null,
  triggering: false,
  wsConnected: true,
  wsSetupError: null,
  triggerMeeting: vi.fn().mockResolvedValue([]),
}

let hookReturn = { ...defaultHookReturn }

const getMeetingsData = vi.fn(() => hookReturn)
vi.mock('@/hooks/useMeetingsData', () => {
  const hookName = 'useMeetingsData'
  return { [hookName]: () => getMeetingsData() }
})

// Static import: vi.mock is hoisted so the mock is applied before import
import MeetingsPage from '@/pages/MeetingsPage'

function renderMeetings() {
  return render(
    <MemoryRouter>
      <MeetingsPage />
    </MemoryRouter>,
  )
}

describe('MeetingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    hookReturn = { ...defaultHookReturn, triggerMeeting: vi.fn().mockResolvedValue([]) }
  })

  it('renders page heading', () => {
    renderMeetings()
    expect(screen.getByText('Meetings')).toBeInTheDocument()
  })

  it('renders loading skeleton when loading with no data', () => {
    hookReturn = { ...defaultHookReturn, loading: true, meetings: [] }
    renderMeetings()
    expect(screen.getByLabelText('Loading meetings')).toBeInTheDocument()
  })

  it('renders metric cards', () => {
    renderMeetings()
    expect(screen.getByText('TOTAL MEETINGS')).toBeInTheDocument()
    expect(screen.getByText('IN PROGRESS')).toBeInTheDocument()
    expect(screen.getByText('COMPLETED')).toBeInTheDocument()
    expect(screen.getByText('TOTAL TOKENS')).toBeInTheDocument()
  })

  it('renders meeting cards when data present', () => {
    renderMeetings()
    // Text appears in both timeline nodes and cards
    expect(screen.getAllByText('Daily Standup').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Sprint Planning').length).toBeGreaterThanOrEqual(1)
  })

  it('shows error banner when error is set', () => {
    hookReturn = { ...defaultHookReturn, error: 'Connection lost' }
    renderMeetings()
    expect(screen.getByText('Connection lost')).toBeInTheDocument()
  })

  it('shows custom wsSetupError message when provided', () => {
    hookReturn = { ...defaultHookReturn, wsConnected: false, wsSetupError: 'WebSocket auth failed' }
    renderMeetings()
    expect(screen.getByText('WebSocket auth failed')).toBeInTheDocument()
  })

  it('does not show skeleton when loading but data already exists', () => {
    hookReturn = { ...defaultHookReturn, loading: true }
    renderMeetings()
    expect(screen.getByText('Meetings')).toBeInTheDocument()
    expect(screen.queryByLabelText('Loading meetings')).not.toBeInTheDocument()
  })

  it('shows empty state when no meetings', () => {
    hookReturn = { ...defaultHookReturn, meetings: [], total: 0 }
    renderMeetings()
    expect(screen.getByText('No meetings yet')).toBeInTheDocument()
  })

  it('renders trigger meeting button', () => {
    renderMeetings()
    // ListHeader shows "Trigger meeting" (sentence case per consistent button labelling)
    expect(
      screen.getAllByRole('button', { name: /trigger meeting/i }).length,
    ).toBeGreaterThanOrEqual(1)
  })
})
