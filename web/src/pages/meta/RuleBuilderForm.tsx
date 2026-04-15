import { useMemo, useState } from 'react'

import { createLogger } from '@/lib/logger'
import { Button } from '@/components/ui/button'
import { InputField } from '@/components/ui/input-field'
import { SelectField } from '@/components/ui/select-field'
import { SegmentedControl } from '@/components/ui/segmented-control'
import { SliderField } from '@/components/ui/slider-field'
import { useCustomRulesStore } from '@/stores/custom-rules'
import { useToastStore } from '@/stores/toast'
import { getErrorMessage } from '@/utils/errors'
import type {
  Comparator,
  CreateCustomRuleRequest,
  CustomRule,
  MetricDescriptor,
  ProposalAltitude,
  RuleSeverity,
} from '@/api/endpoints/custom-rules'

import { RulePreviewPanel } from './RulePreviewPanel'

const log = createLogger('rule-builder-form')

const COMPARATOR_OPTIONS: { value: Comparator; label: string }[] = [
  { value: 'lt', label: '<' },
  { value: 'le', label: '<=' },
  { value: 'gt', label: '>' },
  { value: 'ge', label: '>=' },
  { value: 'eq', label: '=' },
  { value: 'ne', label: '!=' },
]

const SEVERITY_OPTIONS: { value: RuleSeverity; label: string }[] = [
  { value: 'info', label: 'Info' },
  { value: 'warning', label: 'Warning' },
  { value: 'critical', label: 'Critical' },
]

const ALTITUDE_OPTIONS: { value: ProposalAltitude; label: string }[] = [
  { value: 'config_tuning', label: 'Config Tuning' },
  { value: 'architecture', label: 'Architecture' },
  { value: 'prompt_tuning', label: 'Prompt Tuning' },
]

function AltitudeOptionRow({
  option,
  checked,
  onToggle,
}: {
  option: { value: ProposalAltitude; label: string }
  checked: boolean
  onToggle: (checked: boolean) => void
}) {
  return (
    <label className="flex items-center gap-2 text-body-sm text-foreground">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onToggle(e.target.checked)}
        className="accent-accent"
      />
      {option.label}
    </label>
  )
}

interface FormState {
  name: string
  description: string
  metric_path: string
  comparator: Comparator
  threshold: string
  severity: RuleSeverity
  target_altitudes: Set<ProposalAltitude>
}

const INITIAL_FORM: FormState = {
  name: '',
  description: '',
  metric_path: '',
  comparator: 'lt',
  threshold: '0',
  severity: 'warning',
  target_altitudes: new Set(['config_tuning']),
}

function formFromRule(rule: CustomRule): FormState {
  return {
    name: rule.name,
    description: rule.description,
    metric_path: rule.metric_path,
    comparator: rule.comparator,
    threshold: String(rule.threshold),
    severity: rule.severity,
    target_altitudes: new Set(rule.target_altitudes),
  }
}

interface RuleBuilderFormProps {
  /** Rule to edit (null = create mode). */
  editRule: CustomRule | null
  /** Available metrics. */
  metrics: readonly MetricDescriptor[]
  /** Called when the form is submitted or cancelled. */
  onClose: () => void
}

export function RuleBuilderForm({ editRule, metrics, onClose }: RuleBuilderFormProps) {
  const isEdit = editRule !== null
  const [form, setForm] = useState<FormState>(
    () => (editRule ? formFromRule(editRule) : INITIAL_FORM),
  )
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({})
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const createRule = useCustomRulesStore((s) => s.createRule)
  const updateRule = useCustomRulesStore((s) => s.updateRule)

  function updateField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
    setErrors((prev) => ({ ...prev, [key]: undefined }))
    setSubmitError(null)
  }

  const selectedMetric = useMemo(
    () => metrics.find((m) => m.path === form.metric_path) ?? null,
    [metrics, form.metric_path],
  )

  // Flatten metrics into SelectOption format.
  const metricSelectOptions = useMemo(
    () =>
      metrics.map((m) => ({
        value: m.path,
        label: `${m.label}${m.unit ? ` (${m.unit})` : ''} -- ${m.domain}`,
      })),
    [metrics],
  )

  const thresholdNum = parseFloat(form.threshold)
  const sliderMin = selectedMetric?.min_value ?? 0
  const sliderMax = selectedMetric?.max_value ?? Math.max(100, thresholdNum * 2 || 100)

  async function handleSubmit() {
    // Validate
    const next: Partial<Record<keyof FormState, string>> = {}
    if (!form.name.trim()) next.name = 'Name is required'
    if (!form.description.trim()) next.description = 'Description is required'
    if (!form.metric_path) next.metric_path = 'Select a metric'
    const parsed = parseFloat(form.threshold)
    if (!Number.isFinite(parsed)) next.threshold = 'Enter a valid number'
    if (form.target_altitudes.size === 0) {
      next.target_altitudes = 'Select at least one altitude'
    }
    setErrors(next)
    if (Object.keys(next).length > 0) {
      log.debug('Rule form validation failed', next)
      return
    }

    const data: CreateCustomRuleRequest = {
      name: form.name.trim(),
      description: form.description.trim(),
      metric_path: form.metric_path,
      comparator: form.comparator,
      threshold: parsed,
      severity: form.severity,
      target_altitudes: [...form.target_altitudes],
    }

    setSubmitting(true)
    try {
      if (isEdit && editRule) {
        await updateRule(editRule.id, data)
        useToastStore.getState().add({
          variant: 'success',
          title: 'Rule updated',
        })
      } else {
        await createRule(data)
        useToastStore.getState().add({
          variant: 'success',
          title: 'Rule created',
        })
      }
      onClose()
    } catch (err) {
      setSubmitError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-sm font-semibold text-foreground">
        {isEdit ? 'Edit Rule' : 'Create Rule'}
      </h3>

      <InputField
        label="Name"
        value={form.name}
        onChange={(e) => updateField('name', e.target.value)}
        error={errors.name}
        placeholder="e.g. quality-alert"
      />

      <InputField
        label="Description"
        value={form.description}
        onChange={(e) => updateField('description', e.target.value)}
        error={errors.description}
        placeholder="What does this rule detect?"
        multiline
      />

      <SelectField
        label="Metric"
        options={metricSelectOptions}
        value={form.metric_path}
        onChange={(v) => updateField('metric_path', v)}
        error={errors.metric_path}
        placeholder="Select a metric"
      />

      <SegmentedControl
        label="Comparator"
        options={COMPARATOR_OPTIONS}
        value={form.comparator}
        onChange={(v) => updateField('comparator', v)}
        size="sm"
      />

      {selectedMetric &&
        selectedMetric.min_value != null &&
        selectedMetric.max_value != null && (
          <SliderField
            label="Threshold"
            min={sliderMin}
            max={sliderMax}
            step={selectedMetric.value_type === 'int' ? 1 : 0.01}
            value={Number.isFinite(thresholdNum) ? thresholdNum : sliderMin}
            onChange={(v) => updateField('threshold', String(v))}
            formatValue={(v) =>
              selectedMetric.value_type === 'int'
                ? String(Math.round(v))
                : v.toFixed(2)
            }
          />
        )}

      <InputField
        label={selectedMetric?.min_value != null && selectedMetric.max_value != null
          ? 'Threshold (exact)'
          : 'Threshold'}
        type="number"
        value={form.threshold}
        onChange={(e) => updateField('threshold', e.target.value)}
        error={errors.threshold}
        hint={selectedMetric?.unit ? `Unit: ${selectedMetric.unit}` : undefined}
      />

      <SegmentedControl
        label="Severity"
        options={SEVERITY_OPTIONS}
        value={form.severity}
        onChange={(v) => updateField('severity', v)}
        size="sm"
      />

      <fieldset>
        <legend className="mb-1 text-body-sm font-medium text-foreground">
          Target Altitudes
        </legend>
        {errors.target_altitudes && (
          <p className="mb-1 text-body-sm text-danger">
            {errors.target_altitudes}
          </p>
        )}
        <div className="flex flex-col gap-1">
          {ALTITUDE_OPTIONS.map((opt) => (
            <AltitudeOptionRow
              key={opt.value}
              option={opt}
              checked={form.target_altitudes.has(opt.value)}
              onToggle={(checked) => {
                const next = new Set(form.target_altitudes)
                if (checked) next.add(opt.value)
                else next.delete(opt.value)
                updateField('target_altitudes', next)
              }}
            />
          ))}
        </div>
      </fieldset>

      <RulePreviewPanel
        metricPath={form.metric_path || null}
        comparator={form.metric_path ? form.comparator : null}
        threshold={thresholdNum}
        metricLabel={selectedMetric?.label}
      />

      {submitError && (
        <p className="text-sm text-danger">{submitError}</p>
      )}

      <div className="flex gap-2">
        <Button variant="ghost" onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} disabled={submitting}>
          {submitting
            ? isEdit
              ? 'Saving...'
              : 'Creating...'
            : isEdit
              ? 'Save'
              : 'Create'}
        </Button>
      </div>
    </div>
  )
}
