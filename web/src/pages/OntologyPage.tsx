/**
 * Ontology page -- entity catalog + drift monitor.
 */
import { AlertTriangle } from 'lucide-react'
import { useOntologyData } from '@/hooks/useOntologyData'
import { EntityCatalog } from './ontology/EntityCatalog'
import { DriftMonitor } from './ontology/DriftMonitor'
import { OntologySkeleton } from './ontology/OntologySkeleton'

export default function OntologyPage() {
  const {
    filteredEntities,
    totalEntities,
    entitiesLoading,
    entitiesError,
    driftReports,
    driftLoading,
    driftError,
    coreCount,
    userCount,
  } = useOntologyData()

  if (entitiesLoading && totalEntities === 0) {
    return <OntologySkeleton />
  }

  return (
    <div className="space-y-section-gap">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Ontology</h1>
          <p className="text-sm text-muted-foreground">
            Entity definitions, versioning, and semantic drift monitoring
          </p>
        </div>
        <span className="text-sm text-muted-foreground">
          {totalEntities} entities ({coreCount} core, {userCount} user)
        </span>
      </div>

      {/* Error alert */}
      {entitiesError && (
        <div
          role="alert"
          aria-live="assertive"
          className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 p-card text-sm text-danger"
        >
          <AlertTriangle className="size-4 shrink-0" />
          {entitiesError}
        </div>
      )}

      {/* Entity Catalog */}
      <EntityCatalog entities={filteredEntities} />

      {/* Drift Monitor */}
      <DriftMonitor
        reports={driftReports}
        loading={driftLoading}
        error={driftError}
      />
    </div>
  )
}
