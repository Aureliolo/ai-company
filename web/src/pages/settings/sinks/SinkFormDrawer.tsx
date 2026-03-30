import { useCallback, useState } from 'react'
import type { SinkInfo, TestSinkResult } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Drawer } from '@/components/ui/drawer'
import { SelectField } from '@/components/ui/select-field'
import { TagInput } from '@/components/ui/tag-input'
import { ToggleField } from '@/components/ui/toggle-field'

const LOG_LEVELS = [
  { value: 'debug', label: 'Debug' },
  { value: 'info', label: 'Info' },
  { value: 'warning', label: 'Warning' },
  { value: 'error', label: 'Error' },
  { value: 'critical', label: 'Critical' },
]

export interface SinkFormDrawerProps {
  open: boolean
  onClose: () => void
  sink: SinkInfo | null
  onTest: (data: { sink_overrides: string; custom_sinks: string }) => Promise<TestSinkResult>
}

export function SinkFormDrawer({ open, onClose, sink, onTest }: SinkFormDrawerProps) {
  const [level, setLevel] = useState(sink?.level ?? 'info')
  const [jsonFormat, setJsonFormat] = useState(sink?.json_format ?? false)
  const [routingPrefixes, setRoutingPrefixes] = useState<string[]>(
    sink?.routing_prefixes ? [...sink.routing_prefixes] : [],
  )
  const [testResult, setTestResult] = useState<TestSinkResult | null>(null)
  const [testing, setTesting] = useState(false)

  const handleTest = useCallback(async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const overrides = sink?.is_default
        ? JSON.stringify({ [sink.identifier]: { level, json_format: jsonFormat } })
        : '{}'
      const customSinks = !sink?.is_default && sink
        ? JSON.stringify([{
          file_path: sink.identifier,
          level,
          json_format: jsonFormat,
          routing_prefixes: routingPrefixes,
        }])
        : '[]'
      const result = await onTest({ sink_overrides: overrides, custom_sinks: customSinks })
      setTestResult(result)
    } catch {
      setTestResult({ valid: false, error: 'Test request failed' })
    } finally {
      setTesting(false)
    }
  }, [sink, level, jsonFormat, routingPrefixes, onTest])

  return (
    <Drawer open={open} onClose={onClose} title={sink ? `Edit: ${sink.identifier}` : 'New Sink'}>
      <div className="space-y-4 p-4">
        <div className="space-y-1">
          <span className="text-xs font-medium text-text-secondary">Identifier</span>
          <p className="font-mono text-sm text-foreground">{sink?.identifier ?? 'New'}</p>
        </div>

        <SelectField
          label="Level"
          options={LOG_LEVELS}
          value={level}
          onChange={setLevel}
        />

        <ToggleField
          label="JSON format"
          checked={jsonFormat}
          onChange={setJsonFormat}
        />

        {!sink?.is_default && (
          <div className="space-y-1">
            <span className="text-xs font-medium text-text-secondary">Routing Prefixes</span>
            <TagInput
              value={routingPrefixes}
              onChange={setRoutingPrefixes}
              placeholder="Add prefix..."
            />
          </div>
        )}

        <div className="flex items-center gap-2 pt-2">
          <Button variant="ghost" size="sm" onClick={handleTest} disabled={testing}>
            {testing ? 'Testing...' : 'Test Config'}
          </Button>
          {testResult && (
            <span className={`text-xs ${testResult.valid ? 'text-success' : 'text-danger'}`}>
              {testResult.valid ? 'Valid' : testResult.error}
            </span>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button>
          <Button size="sm" onClick={onClose}>Done</Button>
        </div>
      </div>
    </Drawer>
  )
}
