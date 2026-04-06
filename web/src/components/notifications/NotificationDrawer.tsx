import { useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Drawer } from '@/components/ui/drawer'
import { LiveRegion } from '@/components/ui/live-region'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { useNotificationsStore } from '@/stores/notifications'
import type { NotificationFilterGroup } from '@/types/notifications'
import { CATEGORY_CONFIGS } from '@/types/notifications'

import { NotificationEmptyState } from './NotificationEmptyState'
import { NotificationFilterBar } from './NotificationFilterBar'
import { NotificationItemCard } from './NotificationItemCard'

interface NotificationDrawerProps {
  readonly open: boolean
  readonly onClose: () => void
}

export function NotificationDrawer({ open, onClose }: NotificationDrawerProps) {
  const items = useNotificationsStore((s) => s.items)
  const markRead = useNotificationsStore((s) => s.markRead)
  const dismiss = useNotificationsStore((s) => s.dismiss)

  const [filter, setFilter] = useState<NotificationFilterGroup>('all')

  const filteredItems = useMemo(() => {
    if (filter === 'all') return items
    return items.filter(
      (item) => CATEGORY_CONFIGS[item.category].group === filter,
    )
  }, [items, filter])

  const filteredUnreadCount = useMemo(
    () => filteredItems.filter((item) => !item.read).length,
    [filteredItems],
  )

  function handleMarkAllRead() {
    for (const item of filteredItems) {
      if (!item.read) markRead(item.id)
    }
  }

  function handleClearAll() {
    for (const item of filteredItems) {
      dismiss(item.id)
    }
  }

  return (
    <Drawer open={open} onClose={onClose} title="Notifications" side="right">
      <div className="flex h-full flex-col gap-3 p-card">
        {/* Filter bar */}
        <NotificationFilterBar value={filter} onChange={setFilter} />

        {/* Summary row */}
        <div className="flex items-center justify-between">
          <LiveRegion>
            <span className="text-xs text-muted-foreground">
              {filteredUnreadCount > 0
                ? `${filteredUnreadCount} unread`
                : 'All read'}
            </span>
          </LiveRegion>
          {filteredUnreadCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleMarkAllRead}
              className="text-xs"
            >
              Mark all read
            </Button>
          )}
        </div>

        {/* Notification list */}
        <div className="flex-1 overflow-y-auto">
          {filteredItems.length === 0 ? (
            <NotificationEmptyState filter={filter} />
          ) : (
            <StaggerGroup className="flex flex-col gap-1" role="list">
              {filteredItems.map((item) => (
                <StaggerItem key={item.id}>
                  <NotificationItemCard
                    item={item}
                    onMarkRead={markRead}
                    onDismiss={dismiss}
                  />
                </StaggerItem>
              ))}
            </StaggerGroup>
          )}
        </div>

        {/* Footer */}
        {filteredItems.length > 0 && (
          <div className="border-t border-border pt-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClearAll}
              className="w-full text-xs text-muted-foreground"
            >
              Clear all
            </Button>
          </div>
        )}
      </div>
    </Drawer>
  )
}
