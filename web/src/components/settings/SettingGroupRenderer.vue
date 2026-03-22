<script setup lang="ts">
import { computed } from 'vue'
import SettingField from './SettingField.vue'
import { HIDDEN_SETTINGS } from '@/utils/constants'
import type { SettingEntry, SettingNamespace } from '@/api/types'

const props = defineProps<{
  entries: SettingEntry[]
  showAdvanced: boolean
  savingKey?: string | null
}>()

const emit = defineEmits<{
  save: [entry: SettingEntry, value: string]
  reset: [entry: SettingEntry]
  dirty: [payload: { namespace: SettingNamespace; key: string; value: string; isDirty: boolean }]
}>()

/** Whether a setting is hidden from the GUI (system-managed). */
function isHidden(e: SettingEntry): boolean {
  return HIDDEN_SETTINGS.has(`${e.definition.namespace}/${e.definition.key}`)
}

/** Basic entries (always visible, excluding hidden). */
const basicEntries = computed(() =>
  props.entries.filter((e) => e.definition.level === 'basic' && !isHidden(e)),
)

/** Advanced entries (visible only when showAdvanced is true, excluding hidden). */
const advancedEntries = computed(() => {
  if (!props.showAdvanced) return []
  return props.entries.filter((e) => e.definition.level === 'advanced' && !isHidden(e))
})

/** Group entries by their definition.group field. */
function buildGroups(entries: SettingEntry[]): Map<string, SettingEntry[]> {
  const map = new Map<string, SettingEntry[]>()
  for (const entry of entries) {
    const group = entry.definition.group
    const list = map.get(group)
    if (list) {
      list.push(entry)
    } else {
      map.set(group, [entry])
    }
  }
  return map
}

const basicGroups = computed(() => buildGroups(basicEntries.value))
const advancedGroups = computed(() => buildGroups(advancedEntries.value))

/** Whether a setting should span full width (JSON types need more space). */
function isWide(entry: SettingEntry): boolean {
  return entry.definition.type === 'json'
}

function handleSave(entry: SettingEntry, value: string) {
  emit('save', entry, value)
}

function handleReset(entry: SettingEntry) {
  emit('reset', entry)
}

interface DirtyPayload {
  namespace: SettingNamespace
  key: string
  value: string
  isDirty: boolean
}

function handleDirty(payload: DirtyPayload) {
  emit('dirty', payload)
}
</script>

<template>
  <div
    v-if="basicEntries.length === 0 && advancedEntries.length === 0"
    class="rounded-lg border border-dashed border-slate-700 p-8 text-center"
  >
    <p class="text-sm text-slate-400">No settings available in this section.</p>
  </div>

  <div v-else class="space-y-6">
    <!-- Basic settings -->
    <fieldset v-for="[groupName, groupEntries] in basicGroups" :key="groupName">
      <legend class="mb-3 text-sm font-semibold text-slate-300">{{ groupName }}</legend>
      <div class="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <SettingField
          v-for="entry in groupEntries"
          :key="`${entry.definition.namespace}/${entry.definition.key}`"
          :entry="entry"
          :saving="savingKey === `${entry.definition.namespace}/${entry.definition.key}`"
          :class="{ 'xl:col-span-2': isWide(entry) }"
          @save="(value: string) => handleSave(entry, value)"
          @reset="handleReset(entry)"
          @dirty="handleDirty"
        />
      </div>
    </fieldset>

    <!-- Advanced settings divider + section -->
    <template v-if="advancedEntries.length > 0">
      <div class="flex items-center gap-3 border-t-2 border-amber-500/50 pt-4">
        <i class="pi pi-exclamation-triangle text-amber-400" aria-hidden="true" />
        <span class="text-sm font-semibold text-amber-400">Advanced Settings</span>
      </div>

      <fieldset v-for="[groupName, groupEntries] in advancedGroups" :key="`adv-${groupName}`">
        <legend class="mb-3 text-sm font-semibold text-amber-300/80">{{ groupName }}</legend>
        <div class="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <SettingField
            v-for="entry in groupEntries"
            :key="`${entry.definition.namespace}/${entry.definition.key}`"
            :entry="entry"
            :saving="savingKey === `${entry.definition.namespace}/${entry.definition.key}`"
            :is-advanced="true"
            :class="{ 'xl:col-span-2': isWide(entry) }"
            @save="(value: string) => handleSave(entry, value)"
            @reset="handleReset(entry)"
            @dirty="handleDirty"
          />
        </div>
      </fieldset>
    </template>
  </div>
</template>
