import { useEffect } from 'react'
import { Bell } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { SectionCard } from '@/components/ui/section-card'
import { ToggleField } from '@/components/ui/toggle-field'
import * as browserNotifications from '@/services/browser-notifications'
import { useNotificationsStore } from '@/stores/notifications'
import type { NotificationCategory, NotificationRoute } from '@/types/notifications'
import { CATEGORY_CONFIGS, FILTER_GROUP_LABELS } from '@/types/notifications'

const CATEGORIES = Object.keys(CATEGORY_CONFIGS) as NotificationCategory[]

const GROUPS = [...new Set(CATEGORIES.map((c) => CATEGORY_CONFIGS[c].group))]

function routeEnabled(
  category: NotificationCategory,
  route: NotificationRoute,
  overrides: Partial<Record<NotificationCategory, readonly NotificationRoute[]>>,
): boolean {
  const routes = overrides[category] ?? CATEGORY_CONFIGS[category].defaultRoutes
  return routes.includes(route)
}

export function NotificationsSection() {
  const preferences = useNotificationsStore((s) => s.preferences)
  const setGlobalMute = useNotificationsStore((s) => s.setGlobalMute)
  const setRouteOverride = useNotificationsStore((s) => s.setRouteOverride)
  const setBrowserPermission = useNotificationsStore((s) => s.setBrowserPermission)

  // Sync browser permission state on mount -- the actual permission may have
  // changed externally (e.g. user toggled it in browser site settings).
  useEffect(() => {
    if (typeof Notification !== 'undefined') {
      const actual = Notification.permission
      if (actual !== preferences.browserPermission) {
        setBrowserPermission(actual)
      }
    }
    // Only run on mount
    // eslint-disable-next-line @eslint-react/exhaustive-deps
  }, [])

  const permission = preferences.browserPermission

  async function handleRequestPermission() {
    const result = await browserNotifications.requestPermission()
    setBrowserPermission(result)
  }

  function toggleRoute(
    category: NotificationCategory,
    route: NotificationRoute,
    enabled: boolean,
  ) {
    const current = preferences.routeOverrides[category] ?? [...CATEGORY_CONFIGS[category].defaultRoutes]
    const routes = enabled
      ? current.includes(route) ? current : [...current, route]
      : current.filter((r) => r !== route)
    setRouteOverride(category, routes)
  }

  return (
    <SectionCard title="Notifications" icon={Bell}>
      <div className="flex flex-col gap-section-gap">
        {/* Global mute */}
        <ToggleField
          label="Mute all notifications"
          description="Suppress toasts and browser notifications. Drawer history still accumulates."
          checked={preferences.globalMute}
          onChange={setGlobalMute}
        />

        {/* Browser permission */}
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium text-foreground">Browser notifications</p>
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground">
              Permission: {permission}
            </span>
            {permission === 'default' && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => void handleRequestPermission()}
              >
                Enable
              </Button>
            )}
            {permission === 'denied' && (
              <span className="text-xs text-danger">
                Blocked -- enable in browser site settings
              </span>
            )}
          </div>
        </div>

        {/* Per-category routing */}
        <div className="flex flex-col gap-4">
          <p className="text-sm font-medium text-foreground">Per-category routing</p>
          {GROUPS.map((group) => (
            <div key={group} className="flex flex-col gap-2">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                {FILTER_GROUP_LABELS[group]}
              </p>
              {CATEGORIES.filter((c) => CATEGORY_CONFIGS[c].group === group).map(
                (category) => (
                  <div
                    key={category}
                    className="flex items-center justify-between gap-4 rounded-md px-2 py-1 text-sm"
                  >
                    <span className="text-foreground">
                      {CATEGORY_CONFIGS[category].label}
                    </span>
                    <div className="flex gap-3">
                      {(['drawer', 'toast', 'browser'] as const).map((route) => (
                        <label
                          key={route}
                          className="flex items-center gap-1 text-xs text-muted-foreground"
                        >
                          <input
                            type="checkbox"
                            checked={routeEnabled(category, route, preferences.routeOverrides)}
                            onChange={(e) => toggleRoute(category, route, e.target.checked)}
                            className="accent-accent"
                          />
                          {route}
                        </label>
                      ))}
                    </div>
                  </div>
                ),
              )}
            </div>
          ))}
        </div>
      </div>
    </SectionCard>
  )
}
