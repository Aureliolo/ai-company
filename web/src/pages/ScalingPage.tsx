import { AlertTriangle, WifiOff } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { useScalingData } from '@/hooks/useScalingData'
import { useToastStore } from '@/stores/toast'

import { DecisionHistory } from './scaling/DecisionHistory'
import { ScalingMetrics } from './scaling/ScalingMetrics'
import { ScalingSkeleton } from './scaling/ScalingSkeleton'
import { SignalGauges } from './scaling/SignalGauges'
import { StrategyControls } from './scaling/StrategyControls'

export default function ScalingPage() {
  const {
    strategies,
    decisions,
    signals,
    loading,
    error,
    evaluating,
    wsConnected,
    evaluateNow,
  } = useScalingData()

  const addToast = useToastStore((s) => s.add)

  const handleEvaluateNow = async () => {
    const results = await evaluateNow()
    if (results.length > 0) {
      addToast({
        variant: 'success',
        title: `Evaluation produced ${results.length} decision(s)`,
      })
    } else {
      addToast({
        variant: 'info',
        title: 'Evaluation produced no decisions',
      })
    }
  }

  if (loading && strategies.length === 0) {
    return <ScalingSkeleton />
  }

  return (
    <div className="flex flex-col gap-section-gap p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-foreground">
          Dynamic Scaling
        </h1>
        <Button
          onClick={handleEvaluateNow}
          disabled={evaluating}
        >
          {evaluating ? 'Evaluating...' : 'Evaluate Now'}
        </Button>
      </div>

      {/* Error banner */}
      {error && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-md bg-danger/10 p-card text-danger"
        >
          <AlertTriangle className="size-5 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {/* WebSocket disconnection warning */}
      {!wsConnected && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-md bg-warning/10 p-card text-warning"
        >
          <WifiOff className="size-5 shrink-0" aria-hidden="true" />
          <span>Real-time updates unavailable</span>
        </div>
      )}

      {/* Top metrics */}
      <ErrorBoundary level="section">
        <ScalingMetrics
          strategies={strategies}
          decisions={decisions}
          signals={signals}
        />
      </ErrorBoundary>

      {/* Signal gauges and strategy controls side by side */}
      <div className="grid grid-cols-2 gap-card-gap">
        <ErrorBoundary level="section">
          <SignalGauges signals={signals} />
        </ErrorBoundary>
        <ErrorBoundary level="section">
          <StrategyControls strategies={strategies} />
        </ErrorBoundary>
      </div>

      {/* Recent decisions */}
      <ErrorBoundary level="section">
        <DecisionHistory decisions={decisions} />
      </ErrorBoundary>
    </div>
  )
}
