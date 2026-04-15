import { useCallback, useEffect, useRef, useState } from 'react'
import { motion } from 'motion/react'

import { InputField } from '@/components/ui/input-field'
import { createLogger } from '@/lib/logger'
import { useCustomRulesStore } from '@/stores/custom-rules'
import { getErrorMessage } from '@/utils/errors'
import { cardEntrance } from '@/lib/motion'
import type { Comparator, PreviewResult } from '@/api/endpoints/custom-rules'

const log = createLogger('rule-preview-panel')

const COMPARATOR_SYMBOLS: Record<string, string> = {
  lt: '<',
  le: '<=',
  gt: '>',
  ge: '>=',
  eq: '==',
  ne: '!=',
}

interface RulePreviewPanelProps {
  metricPath: string | null
  comparator: Comparator | null
  threshold: number
  metricLabel?: string
}

export function RulePreviewPanel({
  metricPath,
  comparator,
  threshold,
  metricLabel,
}: RulePreviewPanelProps) {
  const [sampleValue, setSampleValue] = useState('')
  const [result, setResult] = useState<PreviewResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const previewRule = useCustomRulesStore((s) => s.previewRule)

  const runPreview = useCallback(
    async (value: number) => {
      if (!metricPath || !comparator) return
      setError(null)
      try {
        const res = await previewRule({
          metric_path: metricPath,
          comparator,
          threshold,
          sample_value: value,
        })
        setResult(res)
      } catch (err) {
        log.error('Preview evaluation failed', err)
        setError(getErrorMessage(err))
        setResult(null)
      }
    },
    [metricPath, comparator, threshold, previewRule],
  )

  useEffect(() => {
    if (!metricPath || !comparator) return
    const parsed = parseFloat(sampleValue)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (!Number.isFinite(parsed) || !Number.isFinite(threshold)) {
      debounceRef.current = setTimeout(() => {
        setResult(null)
        setError(null)
      }, 0)
      return () => {
        if (debounceRef.current) clearTimeout(debounceRef.current)
      }
    }
    debounceRef.current = setTimeout(() => {
      void runPreview(parsed)
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [sampleValue, metricPath, comparator, threshold, runPreview])

  if (!metricPath || !comparator) {
    return (
      <div className="rounded-lg border border-border bg-card/50 p-card text-body-sm text-muted-foreground">
        Select a metric and comparator to preview rule behavior.
      </div>
    )
  }

  const symbol = COMPARATOR_SYMBOLS[comparator] ?? comparator

  return (
    <motion.div
      variants={cardEntrance}
      initial="initial"
      animate="animate"
      className="space-y-3 rounded-lg border border-border bg-card/50 p-card"
    >
      <p className="text-body-sm text-muted-foreground">
        Fire when{' '}
        <span className="font-medium text-foreground">
          {metricLabel ?? metricPath}
        </span>{' '}
        <span className="font-mono text-accent">{symbol} {threshold}</span>
      </p>

      <InputField
        label="Test with sample value"
        type="number"
        value={sampleValue}
        onChange={(e) => setSampleValue(e.target.value)}
        placeholder="Enter a metric value to test"
        hint="The rule will be evaluated against this value"
      />

      {error && (
        <p className="text-body-sm text-danger">{error}</p>
      )}

      {result && (
        <div
          role="status"
          aria-live="polite"
          className={
            result.would_fire
              ? 'rounded-md border border-warning/30 bg-warning/5 p-card text-body-sm text-warning'
              : 'rounded-md border border-success/30 bg-success/5 p-card text-body-sm text-success'
          }
        >
          {result.would_fire
            ? `Would fire: ${result.match?.description ?? 'Rule triggered'}`
            : 'Would NOT fire with this value.'}
        </div>
      )}
    </motion.div>
  )
}
