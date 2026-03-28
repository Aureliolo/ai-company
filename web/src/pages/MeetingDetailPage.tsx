import { useRef } from 'react'
import { useNavigate, useParams } from 'react-router'
import { AlertTriangle, RefreshCw, Video, WifiOff } from 'lucide-react'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { EmptyState } from '@/components/ui/empty-state'
import { SectionCard } from '@/components/ui/section-card'
import { Button } from '@/components/ui/button'
import { useMeetingDetailData } from '@/hooks/useMeetingDetailData'
import { useMeetingsStore } from '@/stores/meetings'
import { ROUTES } from '@/router/routes'
import { MeetingDetailHeader } from './meetings/MeetingDetailHeader'
import { MeetingAgendaSection } from './meetings/MeetingAgendaSection'
import { MeetingTokenBreakdown } from './meetings/MeetingTokenBreakdown'
import { MeetingContributions } from './meetings/MeetingContributions'
import { MeetingDecisions } from './meetings/MeetingDecisions'
import { MeetingActionItems } from './meetings/MeetingActionItems'
import { MeetingDetailSkeleton } from './meetings/MeetingDetailSkeleton'

export default function MeetingDetailPage() {
  const { meetingId } = useParams<{ meetingId: string }>()
  const navigate = useNavigate()
  const {
    meeting,
    loading,
    error,
    wsConnected,
    wsSetupError,
  } = useMeetingDetailData(meetingId ?? '')

  const wasConnectedRef = useRef(false)
  if (wsConnected) wasConnectedRef.current = true

  // Missing meetingId
  if (!meetingId) {
    return (
      <EmptyState
        icon={Video}
        title="Meeting not found"
        description="No meeting ID was provided."
        action={{ label: 'Back to meetings', onClick: () => navigate(ROUTES.MEETINGS) }}
      />
    )
  }

  // Loading state
  if (loading && !meeting) {
    return <MeetingDetailSkeleton />
  }

  // Error state with no data
  if (error && !meeting) {
    return (
      <div className="space-y-6">
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 px-4 py-2 text-sm text-danger">
          <AlertTriangle className="size-4 shrink-0" />
          {error}
        </div>
        <Button
          variant="outline"
          onClick={() => useMeetingsStore.getState().fetchMeeting(meetingId)}
        >
          <RefreshCw className="mr-2 size-4" />
          Retry
        </Button>
      </div>
    )
  }

  if (!meeting) return <MeetingDetailSkeleton />

  return (
    <div className="space-y-6">
      {error && (
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 px-4 py-2 text-sm text-danger">
          <AlertTriangle className="size-4 shrink-0" />
          {error}
        </div>
      )}

      {(wsSetupError || (wasConnectedRef.current && !wsConnected)) && !loading && (
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 px-4 py-2 text-sm text-warning">
          <WifiOff className="size-4 shrink-0" />
          {wsSetupError ?? 'Real-time updates disconnected. Data may be stale.'}
        </div>
      )}

      <ErrorBoundary level="section">
        <MeetingDetailHeader meeting={meeting} />
      </ErrorBoundary>

      {meeting.minutes && (
        <>
          <ErrorBoundary level="section">
            <MeetingAgendaSection agenda={meeting.minutes.agenda} />
          </ErrorBoundary>

          <ErrorBoundary level="section">
            <MeetingTokenBreakdown meeting={meeting} />
          </ErrorBoundary>

          {meeting.minutes.contributions.length > 0 && (
            <ErrorBoundary level="section">
              <MeetingContributions contributions={meeting.minutes.contributions} />
            </ErrorBoundary>
          )}

          <div className="grid grid-cols-1 gap-grid-gap lg:grid-cols-2">
            <ErrorBoundary level="section">
              <MeetingDecisions decisions={meeting.minutes.decisions} />
            </ErrorBoundary>
            <ErrorBoundary level="section">
              <MeetingActionItems actionItems={meeting.minutes.action_items} />
            </ErrorBoundary>
          </div>

          {meeting.minutes.summary && (
            <SectionCard title="Summary">
              <p className="text-sm text-foreground leading-relaxed">
                {meeting.minutes.summary}
              </p>
            </SectionCard>
          )}
        </>
      )}

      {!meeting.minutes && meeting.status === 'in_progress' && (
        <SectionCard title="Meeting In Progress">
          <p className="text-sm text-muted-foreground">
            This meeting is currently in progress. Minutes will be available once the meeting completes.
          </p>
        </SectionCard>
      )}

      {!meeting.minutes && meeting.status === 'scheduled' && (
        <SectionCard title="Meeting Scheduled">
          <p className="text-sm text-muted-foreground">
            This meeting has not started yet. Minutes will be available once the meeting runs.
          </p>
        </SectionCard>
      )}

      {meeting.error_message && (
        <SectionCard title="Error">
          <p className="text-sm text-danger">{meeting.error_message}</p>
        </SectionCard>
      )}
    </div>
  )
}
