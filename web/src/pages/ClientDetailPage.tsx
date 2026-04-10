import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { AlertTriangle, ArrowLeft, Smile, Users } from 'lucide-react'

import {
  getClient,
  getClientSatisfaction,
  type ClientProfile,
  type SatisfactionHistory,
} from '@/api/endpoints/clients'
import { MetricCard } from '@/components/ui/metric-card'
import { SectionCard } from '@/components/ui/section-card'
import { SkeletonCard } from '@/components/ui/skeleton'
import { createLogger } from '@/lib/logger'
import { ROUTES } from '@/router/routes'

const log = createLogger('ClientDetailPage')

/**
 * Detail view for a single simulated client.
 *
 * Shows persona, strictness, domains, and the satisfaction history
 * derived from recorded review feedback.
 */
export default function ClientDetailPage() {
  const { clientId } = useParams<{ clientId: string }>()
  const [client, setClient] = useState<ClientProfile | null>(null)
  const [satisfaction, setSatisfaction] = useState<SatisfactionHistory | null>(
    null,
  )
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [satisfactionError, setSatisfactionError] = useState<string | null>(null)

  useEffect(() => {
    if (!clientId) {
      const timer = setTimeout(() => {
        setError('Missing client id in URL')
        setLoading(false)
      }, 0)
      return () => clearTimeout(timer)
    }
    const load = async () => {
      try {
        const [profile, history] = await Promise.all([
          getClient(clientId),
          getClientSatisfaction(clientId).catch((err) => {
            log.warn('get_client_satisfaction_failed', err)
            setSatisfactionError('Failed to load satisfaction history.')
            return null
          }),
        ])
        setClient(profile)
        setSatisfaction(history)
        setError(null)
      } catch (err) {
        log.error('get_client_failed', err)
        setError('Failed to load client. It may have been removed.')
      } finally {
        setLoading(false)
      }
    }
    void load()
    return undefined
  }, [clientId])

  if (loading) {
    return (
      <div className="space-y-section-gap">
        <SkeletonCard />
      </div>
    )
  }

  if (error || !client) {
    return (
      <div className="space-y-section-gap">
        <Link
          to={ROUTES.CLIENTS}
          className="inline-flex items-center gap-2 text-sm text-accent hover:underline"
        >
          <ArrowLeft className="size-4" />
          Back to clients
        </Link>
        <div
          role="alert"
          aria-live="assertive"
          className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 p-card text-sm text-danger"
        >
          <AlertTriangle className="size-4 shrink-0" />
          {error ?? 'Client not found.'}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-section-gap">
      <Link
        to={ROUTES.CLIENTS}
        className="inline-flex items-center gap-2 text-sm text-accent hover:underline"
      >
        <ArrowLeft className="size-4" />
        Back to clients
      </Link>
      <div>
        <h1 className="text-lg font-semibold text-foreground">{client.name}</h1>
        <p className="text-sm text-text-secondary">{client.client_id}</p>
      </div>
      <SectionCard title="Profile" icon={Users}>
        <dl className="grid grid-cols-1 gap-card md:grid-cols-2">
          <div>
            <dt className="text-xs uppercase text-text-secondary">Persona</dt>
            <dd className="mt-1 text-sm text-foreground">{client.persona}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase text-text-secondary">
              Strictness Level
            </dt>
            <dd className="mt-1 text-sm text-foreground">
              {client.strictness_level.toFixed(2)}
            </dd>
          </div>
          <div className="md:col-span-2">
            <dt className="text-xs uppercase text-text-secondary">
              Expertise Domains
            </dt>
            <dd className="mt-1 text-sm text-foreground">
              {client.expertise_domains.length > 0
                ? client.expertise_domains.join(', ')
                : 'None specified'}
            </dd>
          </div>
        </dl>
      </SectionCard>
      <SectionCard title="Satisfaction" icon={Smile}>
        {satisfactionError && (
          <div
            role="alert"
            aria-live="assertive"
            className="mb-card flex items-center gap-2 rounded-md border border-danger/30 bg-danger/5 p-card text-sm text-danger"
          >
            <AlertTriangle className="size-4 shrink-0" />
            {satisfactionError}
          </div>
        )}
        {satisfaction && satisfaction.total_reviews > 0 ? (
          <div className="space-y-section-gap">
            <div className="grid grid-cols-1 gap-grid-gap md:grid-cols-3">
              <MetricCard
                label="Reviews"
                value={satisfaction.total_reviews.toString()}
              />
              <MetricCard
                label="Acceptance"
                value={`${Math.round(satisfaction.acceptance_rate * 100)}%`}
              />
              <MetricCard
                label="Avg score"
                value={satisfaction.average_score.toFixed(2)}
              />
            </div>
            <ul className="space-y-2">
              {satisfaction.history.slice(0, 10).map((point) => (
                <li
                  key={point.feedback_id}
                  className="flex items-center justify-between rounded-md border border-border bg-card-hover p-card text-sm"
                >
                  <span className="text-foreground">{point.task_id}</span>
                  <span
                    className={
                      point.accepted ? 'text-success' : 'text-danger'
                    }
                  >
                    {point.accepted ? 'accepted' : 'rejected'} ·{' '}
                    {point.score.toFixed(2)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="text-sm text-text-secondary">
            No reviews recorded yet. Run a simulation to populate history.
          </p>
        )}
      </SectionCard>
    </div>
  )
}
