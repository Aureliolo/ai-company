<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import * as yaml from 'js-yaml'
import Button from 'primevue/button'
import CodeEditor from '@/components/common/CodeEditor.vue'
import type { SettingEntry, SettingNamespace } from '@/api/types'

const props = defineProps<{
  entries: SettingEntry[]
  mode: 'json' | 'yaml'
  saving: boolean
}>()

const emit = defineEmits<{
  save: [updates: Array<{ namespace: SettingNamespace; key: string; value: string }>]
}>()

/** Build a flat object from entries for display. */
function entriesToObject(entries: SettingEntry[]): Record<string, unknown> {
  const obj: Record<string, unknown> = {}
  for (const entry of entries) {
    const { key, type } = entry.definition
    if (type === 'json') {
      try { obj[key] = JSON.parse(entry.value) } catch { obj[key] = entry.value }
    } else if (type === 'int') {
      obj[key] = parseInt(entry.value, 10)
    } else if (type === 'float') {
      obj[key] = parseFloat(entry.value)
    } else if (type === 'bool') {
      // Preserve wire format: 'true'/'1' -> true, anything else -> false
      obj[key] = entry.value === 'true' || entry.value === '1'
    } else {
      obj[key] = entry.value
    }
  }
  return obj
}

function serialize(obj: Record<string, unknown>, mode: 'json' | 'yaml'): string {
  if (mode === 'yaml') {
    return yaml.dump(obj, { lineWidth: -1, noRefs: true, quotingType: '"' })
  }
  return JSON.stringify(obj, null, 2)
}

function deserialize(text: string, mode: 'json' | 'yaml'): Record<string, unknown> {
  if (mode === 'yaml') {
    const result = yaml.load(text, { schema: yaml.JSON_SCHEMA })
    if (typeof result !== 'object' || result === null || Array.isArray(result)) {
      throw new Error('YAML must be a mapping')
    }
    return result as Record<string, unknown>
  }
  const result = JSON.parse(text)
  if (typeof result !== 'object' || result === null || Array.isArray(result)) {
    throw new Error('JSON must be an object')
  }
  return result
}

const originalObject = computed(() => entriesToObject(props.entries))
const originalText = computed(() => serialize(originalObject.value, props.mode))

const localText = ref(originalText.value)
const userEditing = ref(false)

// Re-sync when entries or mode change, but only if the user hasn't edited
watch([() => props.entries, () => props.mode], () => {
  if (!userEditing.value) {
    localText.value = serialize(entriesToObject(props.entries), props.mode)
  }
})

// Track user edits vs programmatic changes
watch(localText, (newVal) => {
  userEditing.value = newVal !== originalText.value
})

/** Parse result: either a list of changes or an error string. */
const parseResult = computed<{ changes: Array<{ namespace: SettingNamespace; key: string; value: string }>; error: string | null }>(() => {
  try {
    const parsed = deserialize(localText.value, props.mode)

    // Diff against original
    const changes: Array<{ namespace: SettingNamespace; key: string; value: string }> = []
    for (const entry of props.entries) {
      const { namespace, key, type } = entry.definition
      if (!(key in parsed)) continue
      const newVal = parsed[key]
      let serialized: string
      if (type === 'json') {
        serialized = JSON.stringify(newVal)
      } else if (type === 'bool') {
        // Preserve wire format: compare normalized booleans to avoid
        // bogus diffs when wire format is '1'/'0' vs 'true'/'false'
        const oldBool = entry.value === 'true' || entry.value === '1'
        if (Boolean(newVal) === oldBool) continue
        serialized = String(newVal)
      } else {
        serialized = String(newVal)
      }
      if (serialized !== entry.value) {
        changes.push({ namespace, key, value: serialized })
      }
    }
    return { changes, error: null }
  } catch (err) {
    return { changes: [], error: err instanceof Error ? err.message : 'Invalid content' }
  }
})

const parseError = computed(() => parseResult.value.error)
const parsedChanges = computed(() => parseResult.value.changes)

const isDirty = computed(() => localText.value !== originalText.value)
const canSave = computed(() => isDirty.value && parseError.value === null && parsedChanges.value.length > 0 && !props.saving)

function handleSave() {
  if (!canSave.value) return
  emit('save', parsedChanges.value)
  userEditing.value = false
}
</script>

<template>
  <div class="space-y-3">
    <CodeEditor
      v-model="localText"
      :language="mode"
      min-height="300px"
    />

    <div
      v-if="parseError"
      role="alert"
      class="rounded bg-red-500/10 p-2 text-xs text-red-400"
    >
      {{ parseError }}
    </div>

    <div class="flex items-center gap-3">
      <Button
        label="Save Modified"
        size="small"
        :disabled="!canSave"
        :loading="saving"
        @click="handleSave"
      />
      <span
        v-if="isDirty && !parseError"
        class="text-xs text-slate-400"
      >
        {{ parsedChanges.length }} setting(s) modified
      </span>
    </div>
  </div>
</template>
