import { AlertTriangle, Users, WifiOff } from 'lucide-react'
import { Link } from 'react-router'

import { SectionCard } from '@/components/ui/section-card'
import { EmptyState } from '@/components/ui/empty-state'
import { SkeletonCard } from '@/components/ui/skeleton'
import { useClientsData } from '@/hooks/useClientsData'
import { ROUTES } from '@/router/routes'

/**
 * Client pool list page.
 *
 * Surfaces every simulated client profile with a quick-link to the
 * detail page. Read-only for now; creation and editing flow lands in
 * the follow-up PR that introduces the create drawer.
 */
export default function ClientListPage() {
  const { clients, loading, error, wsConnected } = useClientsData()

  if (loading && clients.length === 0) {
    return (
      <div className="space-y-section-gap">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-foreground">Clients</h1>
        </div>
        <div className="grid grid-cols-1 gap-grid-gap md:grid-cols-2 lg:grid-cols-3">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-section-gap">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-foreground">Clients</h1>
        <span className="text-sm text-muted-foreground">
          {clients.length} total
        </span>
      </div>

      {error && (
        <div
          role="alert"
          aria-live="assertive"
          className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 p-card text-sm text-danger"
        >
          <AlertTriangle className="size-4 shrink-0" />
          {error}
        </div>
      )}

      {!wsConnected && !loading && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 p-card text-sm text-warning"
        >
          <WifiOff className="size-4 shrink-0" />
          Real-time updates disconnected. List refresh may be delayed.
        </div>
      )}

      {clients.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No clients yet"
          description="Create simulated clients via the API to exercise the intake and review pipeline."
        />
      ) : (
        <div className="grid grid-cols-1 gap-grid-gap md:grid-cols-2 lg:grid-cols-3">
          {clients.map((client) => (
            <SectionCard
              key={client.client_id}
              title={client.name}
              icon={Users}
            >
              <div className="space-y-2 text-sm">
                <p className="text-text-secondary">{client.persona}</p>
                <p className="text-text-secondary">
                  <span className="font-medium text-foreground">Strictness:</span>{' '}
                  {client.strictness_level.toFixed(2)}
                </p>
                {client.expertise_domains.length > 0 && (
                  <p className="text-text-secondary">
                    <span className="font-medium text-foreground">Domains:</span>{' '}
                    {client.expertise_domains.join(', ')}
                  </p>
                )}
                <Link
                  to={ROUTES.CLIENT_DETAIL.replace(':clientId', client.client_id)}
                  className="inline-block pt-2 text-accent hover:underline"
                >
                  View details →
                </Link>
              </div>
            </SectionCard>
          ))}
        </div>
      )}
    </div>
  )
}
