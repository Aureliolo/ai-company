import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { AlertTriangle, ArrowLeft, Users } from 'lucide-react'

import { getClient, type ClientProfile } from '@/api/endpoints/clients'
import { SectionCard } from '@/components/ui/section-card'
import { SkeletonCard } from '@/components/ui/skeleton'
import { createLogger } from '@/lib/logger'
import { ROUTES } from '@/router/routes'

const log = createLogger('ClientDetailPage')

/**
 * Detail view for a single simulated client.
 *
 * Shows persona, strictness, domains, and links back to the list.
 * Activity timeline and feedback history charts follow in the next
 * dashboard iteration.
 */
export default function ClientDetailPage() {
  const { clientId } = useParams<{ clientId: string }>()
  const [client, setClient] = useState<ClientProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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
        const profile = await getClient(clientId)
        setClient(profile)
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
    </div>
  )
}
