import { useState } from 'react'
import { useParams } from 'react-router'
import { AlertTriangle, WifiOff } from 'lucide-react'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { SectionCard } from '@/components/ui/section-card'
import { useMeetingDetailData } from '@/hooks/useMeetingDetailData'
import { MeetingDetailHeader } from './meetings/MeetingDetailHeader'
import { MeetingAgendaSection } from './meetings/MeetingAgendaSection'
import { MeetingTokenBreakdown } from './meetings/MeetingTokenBreakdown'
import { MeetingContributions } from './meetings/MeetingContributions'
import { MeetingDecisions } from './meetings/MeetingDecisions'
import { MeetingActionItems } from './meetings/MeetingActionItems'
import { MeetingDetailSkeleton } from './meetings/MeetingDetailSkeleton'

export default function MeetingDetailPage() {
  const { meetingId } = useParams<{ meetingId: string }>()
  const {
    meeting,
    loading,
    error,
    wsConnected,
    wsSetupError,
  } = useMeetingDetailData(meetingId ?? '')

  const [wasConnected, setWasConnected] = useState(false)

  if (wsConnected && !wasConnected) {
    setWasConnected(true)
  }

  // Loading state
  if (loading && !meeting) {
    return <MeetingDetailSkeleton />
  }

  // Error state with no data
  if (error && !meeting) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 px-4 py-2 text-sm text-danger">
          <AlertTriangle className="size-4 shrink-0" />
          {error}
        </div>
      </div>
    )
  }

  if (!meeting) return null

  return (
    <div className="space-y-6">
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 px-4 py-2 text-sm text-danger">
          <AlertTriangle className="size-4 shrink-0" />
          {error}
        </div>
      )}

      {(wsSetupError || (wasConnected && !wsConnected)) && !loading && (
        <div className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 px-4 py-2 text-sm text-warning">
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

          <div className="grid grid-cols-2 gap-grid-gap max-[1023px]:grid-cols-1">
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
