import { useCallback, useEffect, useMemo, useRef } from 'react'
import { Loader2, MessageSquare } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { groupMessagesByDate, groupMessagesByThread, getDateGroupLabel } from '@/utils/messages'
import { TimestampDivider } from './TimestampDivider'
import { MessageThread } from './MessageThread'
import { MessageBubble } from './MessageBubble'
import type { Message } from '@/api/types/messages'

interface MessageListProps {
  messages: Message[]
  expandedThreads: Set<string>
  toggleThread: (taskId: string) => void
  onSelectMessage: (id: string) => void
  hasMore: boolean
  loadingMore: boolean
  onLoadMore: () => void
  newMessageIds?: Set<string>
}

export function MessageList({
  messages,
  expandedThreads,
  toggleThread,
  onSelectMessage,
  hasMore,
  loadingMore,
  onLoadMore,
  newMessageIds,
}: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const wasAtBottomRef = useRef(true)

  // Track whether user is near the bottom
  const handleScroll = useCallback(() => {
    const el = containerRef.current
    if (!el) return
    wasAtBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  }, [])

  // Auto-scroll to bottom when new messages arrive (if user was at bottom)
  const prevLengthRef = useRef(messages.length)
  useEffect(() => {
    if (messages.length > prevLengthRef.current && wasAtBottomRef.current) {
      const el = containerRef.current
      if (el) el.scrollTop = el.scrollHeight
    }
    prevLengthRef.current = messages.length
  }, [messages.length])

  // Sort messages ascending by timestamp for display
  const sorted = useMemo(
    () => [...messages].sort((a, b) => a.timestamp.localeCompare(b.timestamp)),
    [messages],
  )

  const dateGroups = useMemo(() => groupMessagesByDate(sorted), [sorted])

  if (messages.length === 0) {
    return (
      <EmptyState
        icon={MessageSquare}
        title="No messages"
        description="No messages in this channel yet."
      />
    )
  }

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto"
      aria-live="polite"
      aria-label="Messages"
    >
      {/* Load more button */}
      {hasMore && (
        <div className="flex justify-center py-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={onLoadMore}
            disabled={loadingMore}
          >
            {loadingMore && <Loader2 className="size-3 animate-spin" />}
            {loadingMore ? 'Loading...' : 'Load earlier messages'}
          </Button>
        </div>
      )}

      {/* Date-grouped messages */}
      {[...dateGroups.entries()].map(([dateKey, msgs]) => {
        const { threads, standalone } = groupMessagesByThread(msgs)

        return (
          <div key={dateKey}>
            <TimestampDivider label={getDateGroupLabel(dateKey)} />

            {/* Threads */}
            {[...threads.entries()].map(([taskId, threadMsgs]) => (
              <MessageThread
                key={taskId}
                messages={threadMsgs}
                expanded={expandedThreads.has(taskId)}
                onToggle={() => toggleThread(taskId)}
                onSelectMessage={onSelectMessage}
                newMessageIds={newMessageIds}
              />
            ))}

            {/* Standalone messages */}
            {standalone.map((msg) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                isNew={newMessageIds?.has(msg.id)}
                onClick={() => onSelectMessage(msg.id)}
              />
            ))}
          </div>
        )
      })}
    </div>
  )
}
