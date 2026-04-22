import { useCallback, useEffect, useState } from 'react'
import { FileText, Play } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ErrorBanner } from '@/components/ui/error-banner'
import { EmptyState } from '@/components/ui/empty-state'
import { ListHeader } from '@/components/ui/list-header'
import { MetadataGrid } from '@/components/ui/metadata-grid'
import { SectionCard } from '@/components/ui/section-card'
import { Skeleton } from '@/components/ui/skeleton'
import { useToastStore } from '@/stores/toast'
import {
  generateReport,
  listReportPeriods,
  type ReportPeriod,
  type ReportResponse,
} from '@/api/endpoints/reports'
import { createLogger } from '@/lib/logger'
import { getErrorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/format'

const log = createLogger('ReportsPage')

interface GeneratedReportState {
  period: ReportPeriod
  response: ReportResponse
}

export default function ReportsPage() {
  const [periods, setPeriods] = useState<readonly ReportPeriod[] | null>(null)
  const [loadingPeriods, setLoadingPeriods] = useState(true)
  const [periodsError, setPeriodsError] = useState<string | null>(null)
  const [generating, setGenerating] = useState<ReportPeriod | null>(null)
  const [report, setReport] = useState<GeneratedReportState | null>(null)
  const toast = useToastStore((state) => state.add)

  // Shared fetch helper so the initial load and the retry handler
  // emit the same ``log.error`` on failure -- previously the retry
  // handler silently swallowed errors while the initial load logged.
  const fetchPeriods = useCallback(async () => {
    setLoadingPeriods(true)
    setPeriodsError(null)
    try {
      const result = await listReportPeriods()
      setPeriods(result)
    } catch (err) {
      log.error('listReportPeriods', err)
      setPeriodsError(getErrorMessage(err))
    } finally {
      setLoadingPeriods(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const result = await listReportPeriods()
        if (!cancelled) {
          setPeriods(result)
          setPeriodsError(null)
        }
      } catch (err) {
        log.error('listReportPeriods', err)
        if (!cancelled) {
          setPeriodsError(getErrorMessage(err))
        }
      } finally {
        if (!cancelled) {
          setLoadingPeriods(false)
        }
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [])

  const handleGenerate = useCallback(
    async (period: ReportPeriod) => {
      setGenerating(period)
      try {
        const response = await generateReport(period)
        setReport({ period, response })
        toast({
          variant: 'success',
          title: 'Report generated',
          description: `${period} report ready.`,
        })
      } catch (err) {
        log.error('generateReport', err)
        toast({
          variant: 'error',
          title: 'Report generation failed',
          description: getErrorMessage(err),
        })
      } finally {
        setGenerating(null)
      }
    },
    [toast],
  )

  return (
    <div className="space-y-section-gap p-card">
      <ListHeader
        title="Reports"
        count={periods?.length}
        description="Generate on-demand spending, performance, and task completion summaries for a chosen reporting period."
      />

      {periodsError ? (
        <ErrorBanner
          severity="error"
          title="Could not load report periods"
          description={periodsError}
          onRetry={() => void fetchPeriods()}
        />
      ) : loadingPeriods ? (
        <div className="grid grid-cols-1 gap-grid-gap sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      ) : periods && periods.length > 0 ? (
        <div className="grid grid-cols-1 gap-grid-gap sm:grid-cols-2 lg:grid-cols-3">
          {periods.map((period) => (
            <SectionCard
              key={period}
              title={period.charAt(0).toUpperCase() + period.slice(1)}
              icon={FileText}
            >
              <Button
                size="sm"
                onClick={() => void handleGenerate(period)}
                disabled={generating !== null}
              >
                <Play className="size-3" aria-hidden="true" />
                {generating === period ? 'Generating…' : 'Generate'}
              </Button>
            </SectionCard>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={FileText}
          title="No report periods available"
          description="The report service has not published any periods yet."
        />
      )}

      {report ? (
        <SectionCard
          title={`Latest ${report.period} report`}
          icon={FileText}
        >
          <MetadataGrid
            columns={2}
            items={[
              {
                label: 'Start',
                value: formatDateTime(report.response.start),
                valueClassName: 'font-mono',
              },
              {
                label: 'End',
                value: formatDateTime(report.response.end),
                valueClassName: 'font-mono',
              },
              {
                label: 'Sections present',
                value: (
                  <ul className="list-disc pl-4">
                    <li>
                      Spending:{' '}
                      <span
                        className={
                          report.response.has_spending
                            ? 'text-success'
                            : 'text-text-muted'
                        }
                      >
                        {report.response.has_spending ? 'yes' : 'no'}
                      </span>
                    </li>
                    <li>
                      Performance:{' '}
                      <span
                        className={
                          report.response.has_performance
                            ? 'text-success'
                            : 'text-text-muted'
                        }
                      >
                        {report.response.has_performance ? 'yes' : 'no'}
                      </span>
                    </li>
                    <li>
                      Task completion:{' '}
                      <span
                        className={
                          report.response.has_task_completion
                            ? 'text-success'
                            : 'text-text-muted'
                        }
                      >
                        {report.response.has_task_completion ? 'yes' : 'no'}
                      </span>
                    </li>
                    <li>
                      Risk trends:{' '}
                      <span
                        className={
                          report.response.has_risk_trends
                            ? 'text-success'
                            : 'text-text-muted'
                        }
                      >
                        {report.response.has_risk_trends ? 'yes' : 'no'}
                      </span>
                    </li>
                  </ul>
                ),
              },
              {
                label: 'Generated at',
                value: formatDateTime(report.response.generated_at),
                valueClassName: 'font-mono',
              },
            ]}
          />
        </SectionCard>
      ) : null}
    </div>
  )
}
