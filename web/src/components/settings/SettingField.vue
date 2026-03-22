<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Password from 'primevue/password'
import ToggleSwitch from 'primevue/toggleswitch'
import Select from 'primevue/select'
import Textarea from 'primevue/textarea'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import SettingSourceBadge from './SettingSourceBadge.vue'
import SettingRestartBadge from './SettingRestartBadge.vue'
import ChipArrayInput from '@/components/common/ChipArrayInput.vue'
import { validateSettingValue } from '@/stores/settings'
import { SECURITY_SENSITIVE_SETTINGS, SIMPLE_ARRAY_SETTINGS } from '@/utils/constants'
import type { SettingEntry, SettingNamespace } from '@/api/types'

const props = defineProps<{
  entry: SettingEntry
  saving: boolean
  isAdvanced?: boolean
}>()

const emit = defineEmits<{
  save: [value: string]
  reset: []
  dirty: [payload: { namespace: SettingNamespace; key: string; value: string; isDirty: boolean }]
}>()

const def = computed(() => props.entry.definition)

/** Whether this JSON setting is a simple string array with chip input. */
const isSimpleArray = computed(() =>
  def.value.type === 'json' &&
  SIMPLE_ARRAY_SETTINGS.has(`${def.value.namespace}/${def.value.key}`),
)

// Local edit state -- initialized from server value
const localValue = ref(props.entry.value)

// Re-sync local value when server value changes (after save/reset)
watch(() => props.entry.value, (newVal) => {
  localValue.value = newVal
})

// Emit dirty state on every local value change.
// Canonicalize JSON before comparing to avoid false dirty flags
// from formatting differences (e.g. compact vs pretty-printed).
watch(localValue, (val) => {
  let isDirty = val !== props.entry.value
  if (isDirty && def.value.type === 'json') {
    try {
      const a = JSON.parse(val)
      const b = JSON.parse(props.entry.value)
      isDirty = JSON.stringify(a) !== JSON.stringify(b)
    } catch {
      // Parse failure means genuinely different
    }
  }
  emit('dirty', {
    namespace: def.value.namespace,
    key: def.value.key,
    value: val,
    isDirty,
  })
})

// Derived state for simple array (convert JSON string to string[])
const arrayValue = computed({
  get: () => {
    try {
      const parsed = JSON.parse(localValue.value)
      return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === 'string') : []
    } catch {
      return []
    }
  },
  set: (val: string[]) => {
    localValue.value = JSON.stringify(val)
  },
})

// Derived state for bool toggle (convert string to boolean)
const boolValue = computed({
  get: () => localValue.value === 'true',
  set: (val: boolean) => { localValue.value = String(val) },
})

// Derived state for numeric inputs (convert string to number)
const numericValue = computed({
  get: () => {
    const num = Number(localValue.value)
    return isNaN(num) ? null : num
  },
  set: (val: number | null) => {
    localValue.value = val === null ? '' : String(val)
  },
})

// Validation
const validationError = computed(() => validateSettingValue(localValue.value, def.value))

// Dirty tracking -- compare local value to server value
const isDirty = computed(() => localValue.value !== props.entry.value)

// Can save: dirty, valid, and not already saving
const canSave = computed(
  () => !isEnvSourced.value && isDirty.value && validationError.value === null && !props.saving,
)

// Can reset: only if current source is 'db' (has a DB override to delete)
const canReset = computed(() => props.entry.source === 'db' && !props.saving)

/** Whether this setting is sourced from an environment variable (read-only). */
const isEnvSourced = computed(() => props.entry.source === 'env')

/** Whether this setting carries elevated security risk. */
const isSecuritySensitive = computed(
  () => SECURITY_SENSITIVE_SETTINGS.has(`${def.value.namespace}/${def.value.key}`),
)

function handleSave() {
  if (!canSave.value) return
  emit('save', localValue.value)
}

function handleReset() {
  if (!canReset.value) return
  emit('reset')
}

function formatJson() {
  if (isEnvSourced.value) return
  try {
    const parsed = JSON.parse(localValue.value)
    localValue.value = JSON.stringify(parsed, null, 2)
  } catch {
    // Invalid JSON -- do nothing
  }
}
</script>

<template>
  <div
    class="rounded-lg border p-4"
    :class="isAdvanced
      ? 'border-l-4 border-amber-500/30 border-l-amber-500 bg-amber-500/5'
      : 'border-slate-800'"
  >
    <!-- Header row: key name + badges -->
    <div class="mb-2 flex flex-wrap items-center gap-2">
      <span class="text-sm font-medium text-slate-200">{{ def.key }}</span>
      <SettingSourceBadge :source="entry.source" />
      <SettingRestartBadge v-if="def.restart_required" />
      <Tag v-if="def.level === 'advanced'" value="Advanced" severity="warn" />
    </div>

    <!-- Description -->
    <p class="mb-3 text-xs text-slate-400">{{ def.description }}</p>
    <p v-if="isSecuritySensitive" class="mb-2 text-xs text-red-400">
      Security-sensitive setting. Misconfiguration may expose protected endpoints.
    </p>
    <p v-if="isEnvSourced" class="mb-2 text-xs text-amber-400">
      Set via environment variable. Remove the variable to edit here.
    </p>

    <!-- Input based on type -->
    <div class="mb-3">
      <!-- Simple string array (chip input) -->
      <ChipArrayInput
        v-if="isSimpleArray"
        v-model="arrayValue"
        :disabled="saving || isEnvSourced"
        placeholder="Add value..."
      />

      <!-- String (non-sensitive) -->
      <InputText
        v-else-if="def.type === 'str' && !def.sensitive"
        v-model="localValue"
        type="text"
        class="w-full"
        :disabled="saving || isEnvSourced"
      />

      <!-- String (sensitive) -->
      <Password
        v-else-if="def.type === 'str' && def.sensitive"
        v-model="localValue"
        :toggle-mask="true"
        :feedback="false"
        fluid
        :disabled="saving || isEnvSourced"
        :input-props="{ autocomplete: 'off' }"
      />

      <!-- Integer -->
      <InputNumber
        v-else-if="def.type === 'int'"
        v-model="numericValue"
        :min="def.min_value ?? undefined"
        :max="def.max_value ?? undefined"
        :use-grouping="false"
        :min-fraction-digits="0"
        :max-fraction-digits="0"
        class="w-full"
        :disabled="saving || isEnvSourced"
      />

      <!-- Float -->
      <InputNumber
        v-else-if="def.type === 'float'"
        v-model="numericValue"
        :min="def.min_value ?? undefined"
        :max="def.max_value ?? undefined"
        :use-grouping="false"
        class="w-full"
        :disabled="saving || isEnvSourced"
      />

      <!-- Boolean -->
      <ToggleSwitch
        v-else-if="def.type === 'bool'"
        v-model="boolValue"
        :disabled="saving || isEnvSourced"
        :aria-label="def.key"
      />

      <!-- Enum -->
      <Select
        v-else-if="def.type === 'enum'"
        v-model="localValue"
        :options="[...def.enum_values]"
        class="w-full"
        :disabled="saving || isEnvSourced"
        :placeholder="def.default ? `Default: ${def.default}` : 'Select...'"
      />

      <!-- JSON (complex -- raw textarea) -->
      <div v-else-if="def.type === 'json'">
        <Textarea
          v-model="localValue"
          :rows="6"
          class="w-full font-mono text-xs"
          :disabled="saving || isEnvSourced"
        />
        <Button
          label="Format JSON"
          text
          size="small"
          class="mt-1"
          :disabled="saving || isEnvSourced"
          @click="formatJson"
        />
      </div>
    </div>

    <!-- Validation error -->
    <div v-if="validationError && isDirty" role="alert" class="mb-2 rounded bg-red-500/10 p-2 text-xs text-red-400">
      {{ validationError }}
    </div>

    <!-- Actions -->
    <div class="flex gap-2">
      <Button
        label="Save"
        size="small"
        :disabled="!canSave"
        :loading="saving"
        @click="handleSave"
      />
      <Button
        label="Reset"
        size="small"
        severity="secondary"
        text
        :disabled="!canReset"
        @click="handleReset"
      />
    </div>
  </div>
</template>
