<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import ToggleSwitch from 'primevue/toggleswitch'
import Select from 'primevue/select'
import Textarea from 'primevue/textarea'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import SettingSourceBadge from './SettingSourceBadge.vue'
import SettingRestartBadge from './SettingRestartBadge.vue'
import { validateSettingValue } from '@/stores/settings'
import type { SettingEntry } from '@/api/types'

const props = defineProps<{
  entry: SettingEntry
  saving: boolean
}>()

const emit = defineEmits<{
  save: [value: string]
  reset: []
}>()

const def = computed(() => props.entry.definition)

// Local edit state -- initialized from server value
const localValue = ref(props.entry.value)
const showPassword = ref(false)

// Re-sync local value when server value changes (after save/reset)
watch(() => props.entry.value, (newVal) => {
  localValue.value = newVal
  showPassword.value = false
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
const canSave = computed(() => isDirty.value && validationError.value === null && !props.saving)

// Can reset: only if current source is 'db' (has a DB override to delete)
const canReset = computed(() => props.entry.source === 'db' && !props.saving)

function handleSave() {
  if (!canSave.value) return
  emit('save', localValue.value)
}

function handleReset() {
  if (!canReset.value) return
  emit('reset')
}

function formatJson() {
  try {
    const parsed = JSON.parse(localValue.value)
    localValue.value = JSON.stringify(parsed, null, 2)
  } catch {
    // Invalid JSON -- do nothing
  }
}
</script>

<template>
  <div class="rounded-lg border border-slate-800 p-4">
    <!-- Header row: key name + badges -->
    <div class="mb-2 flex flex-wrap items-center gap-2">
      <span class="text-sm font-medium text-slate-200">{{ def.key }}</span>
      <SettingSourceBadge :source="entry.source" />
      <SettingRestartBadge v-if="def.restart_required" />
      <Tag v-if="def.level === 'advanced'" value="Advanced" severity="secondary" />
    </div>

    <!-- Description -->
    <p class="mb-3 text-xs text-slate-400">{{ def.description }}</p>

    <!-- Input based on type -->
    <div class="mb-3">
      <!-- String (non-sensitive) -->
      <InputText
        v-if="def.type === 'str' && !def.sensitive"
        v-model="localValue"
        type="text"
        class="w-full"
        :disabled="saving"
      />

      <!-- String (sensitive) -->
      <div v-else-if="def.type === 'str' && def.sensitive" class="flex gap-2">
        <InputText
          v-model="localValue"
          :type="showPassword ? 'text' : 'password'"
          class="w-full"
          :disabled="saving"
        />
        <Button
          :icon="showPassword ? 'pi pi-eye-slash' : 'pi pi-eye'"
          text
          size="small"
          @click="showPassword = !showPassword"
        />
      </div>

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
        :disabled="saving"
      />

      <!-- Float -->
      <InputNumber
        v-else-if="def.type === 'float'"
        v-model="numericValue"
        :min="def.min_value ?? undefined"
        :max="def.max_value ?? undefined"
        :use-grouping="false"
        class="w-full"
        :disabled="saving"
      />

      <!-- Boolean -->
      <ToggleSwitch
        v-else-if="def.type === 'bool'"
        v-model="boolValue"
        :disabled="saving"
      />

      <!-- Enum -->
      <Select
        v-else-if="def.type === 'enum'"
        v-model="localValue"
        :options="def.enum_values"
        class="w-full"
        :disabled="saving"
      />

      <!-- JSON -->
      <div v-else-if="def.type === 'json'">
        <Textarea
          v-model="localValue"
          :rows="6"
          class="w-full font-mono text-xs"
          :disabled="saving"
        />
        <Button
          label="Format JSON"
          text
          size="small"
          class="mt-1"
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
