import { useCallback } from 'react'
import { Drawer } from '@/components/ui/drawer'
import { InputField } from '@/components/ui/input-field'
import { SelectField } from '@/components/ui/select-field'
import { NODE_CONFIG_SCHEMAS, type ConfigField } from './node-config-schemas'
import type { WorkflowNodeType } from '@/api/types'

export interface WorkflowNodeDrawerProps {
  open: boolean
  onClose: () => void
  nodeId: string | null
  nodeType: WorkflowNodeType | null
  nodeLabel: string
  config: Record<string, unknown>
  onConfigChange: (config: Record<string, unknown>) => void
}

export function WorkflowNodeDrawer({
  open,
  onClose,
  nodeId,
  nodeType,
  nodeLabel,
  config,
  onConfigChange,
}: WorkflowNodeDrawerProps) {
  const fields = nodeType ? NODE_CONFIG_SCHEMAS[nodeType] : []

  const handleFieldChange = useCallback(
    (key: string, value: string, fieldType?: string) => {
      const parsed = fieldType === 'number' && value !== '' ? Number(value) : value
      onConfigChange({ ...config, [key]: parsed })
    },
    [config, onConfigChange],
  )

  return (
    <Drawer
      open={open}
      onClose={onClose}
      side="right"
      title={`${nodeLabel} Properties`}
      ariaLabel={`Edit ${nodeLabel} properties`}
    >
      <div className="flex flex-col gap-4 p-4">
        <div className="text-xs text-muted-foreground">
          ID: {nodeId}
        </div>

        {fields.map((field: ConfigField) => {
          const value = String(config[field.key] ?? '')

          if (field.type === 'select' && field.options) {
            return (
              <SelectField
                key={field.key}
                label={field.label}
                value={value}
                onChange={(v) => handleFieldChange(field.key, v)}
                placeholder={field.placeholder}
                options={[
                  { value: '', label: '-- Select --' },
                  ...field.options.map((opt) => ({ value: opt.value, label: opt.label })),
                ]}
              />
            )
          }

          return (
            <InputField
              key={field.key}
              label={field.label}
              value={value}
              onValueChange={(v) => handleFieldChange(field.key, v, field.type)}
              placeholder={field.placeholder}
              type={field.type === 'number' ? 'number' : 'text'}
            />
          )
        })}

        {fields.length === 0 && (
          <div className="text-sm text-muted-foreground">
            No configurable properties for this node type.
          </div>
        )}
      </div>
    </Drawer>
  )
}
