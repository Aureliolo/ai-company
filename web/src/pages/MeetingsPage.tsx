import { useCallback, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router'
import { AlertTriangle, Video, WifiOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { useMeetingsData } from '@/hooks/useMeetingsData'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/errors'
import { filterMeetings, type MeetingPageFilters } from '@/utils/meetings'
import type { MeetingStatus } from '@/api/types'
import { MeetingMetricCards } from './meetings/MeetingMetricCards'
import { MeetingFilterBar } from './meetings/MeetingFilterBar'
import { MeetingTimeline } from './meetings/MeetingTimeline'
import { MeetingCard } from './meetings/MeetingCard'
import { TriggerMeetingDialog } from './meetings/TriggerMeetingDialog'
import { MeetingsSkeleton } from './meetings/MeetingsSkeleton'

const VALID_STATUSES: ReadonlySet<string> = new Set([
  'scheduled', 'in_progress', 'completed', 'failed', 'cancelled', 'budget_exhausted',
])

export default function MeetingsPage() {
  const {
    meetings,
    loading,
    error,
    triggering,
    wsConnected,
    wsSetupError,
    triggerMeeting,
  } = useMeetingsData()

  const [searchParams, setSearchParams] = useSearchParams()
  const [triggerOpen, setTriggerOpen] = useState(false)
  const [wasConnected, setWasConnected] = useState(false)

  if (wsConnected && !wasConnected) {
    setWasConnected(true)
  }

  // URL-synced filters
  const filters: MeetingPageFilters = useMemo(() => {
    const rawStatus = searchParams.get('status')
    return {
      status: rawStatus && VALID_STATUSES.has(rawStatus) ? rawStatus as MeetingStatus : undefined,
      meetingType: searchParams.get('type') ?? undefined,
    }
  }, [searchParams])

  const handleFiltersChange = useCallback((newFilters: MeetingPageFilters) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete('status')
      next.delete('type')
      if (newFilters.status) next.set('status', newFilters.status)
      if (newFilters.meetingType) next.set('type', newFilters.meetingType)
      return next
    })
  }, [setSearchParams])

  const handleTrigger = useCallback(async (eventName: string) => {
    try {
      await triggerMeeting({ event_name: eventName })
      setTriggerOpen(false)
      useToastStore.getState().add({ variant: 'success', title: 'Meeting triggered' })
    } catch (err) {
      useToastStore.getState().add({ variant: 'error', title: 'Failed to trigger meeting', description: getErrorMessage(err) })
    }
  }, [triggerMeeting])

  // Derived data
  const filtered = useMemo(() => filterMeetings(meetings, filters), [meetings, filters])
  const meetingTypes = useMemo(
    () => [...new Set(meetings.map((m) => m.meeting_type_name))].sort(),
    [meetings],
  )

  const hasFilters = !!(filters.status || filters.meetingType)

  // Loading state
  if (loading && meetings.length === 0) {
    return <MeetingsSkeleton />
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-foreground">Meetings</h1>
        <Button onClick={() => setTriggerOpen(true)}>Trigger Meeting</Button>
      </div>

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

      <MeetingMetricCards meetings={filtered} />

      <MeetingFilterBar
        filters={filters}
        onFiltersChange={handleFiltersChange}
        meetingTypes={meetingTypes}
      />

      <MeetingTimeline meetings={filtered} />

      {filtered.length > 0 && (
        <StaggerGroup className="grid grid-cols-1 gap-grid-gap md:grid-cols-2 lg:grid-cols-3">
          {filtered.map((meeting) => (
            <StaggerItem key={meeting.meeting_id}>
              <MeetingCard meeting={meeting} />
            </StaggerItem>
          ))}
        </StaggerGroup>
      )}

      {filtered.length === 0 && !hasFilters && (
        <EmptyState
          icon={Video}
          title="No meetings yet"
          description="When meetings are scheduled or triggered, they'll appear here."
          action={{ label: 'Trigger Meeting', onClick: () => setTriggerOpen(true) }}
        />
      )}

      {filtered.length === 0 && hasFilters && (
        <EmptyState
          icon={Video}
          title="No matching meetings"
          description="Try adjusting your filters."
          action={{ label: 'Clear filters', onClick: () => handleFiltersChange({}) }}
        />
      )}

      <TriggerMeetingDialog
        open={triggerOpen}
        onOpenChange={setTriggerOpen}
        onConfirm={handleTrigger}
        loading={triggering}
      />
    </div>
  )
}
