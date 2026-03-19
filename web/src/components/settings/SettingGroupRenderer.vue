<script setup lang="ts">
import { computed } from 'vue'
import SettingField from './SettingField.vue'
import type { SettingEntry } from '@/api/types'

const props = defineProps<{
  entries: SettingEntry[]
  showAdvanced: boolean
  savingKey?: string | null
}>()

const emit = defineEmits<{
  save: [entry: SettingEntry, value: string]
  reset: [entry: SettingEntry]
}>()

/** Entries filtered by the current visibility level. */
const visibleEntries = computed(() => {
  if (props.showAdvanced) return props.entries
  return props.entries.filter((e) => e.definition.level === 'basic')
})

/** Group visible entries by their definition.group field. */
const groups = computed(() => {
  const map = new Map<string, SettingEntry[]>()
  for (const entry of visibleEntries.value) {
    const group = entry.definition.group
    const list = map.get(group)
    if (list) {
      list.push(entry)
    } else {
      map.set(group, [entry])
    }
  }
  return map
})

function handleSave(entry: SettingEntry, value: string) {
  emit('save', entry, value)
}

function handleReset(entry: SettingEntry) {
  emit('reset', entry)
}
</script>

<template>
  <div v-if="visibleEntries.length === 0" class="rounded-lg border border-dashed border-slate-700 p-8 text-center">
    <p class="text-sm text-slate-400">No settings available in this section.</p>
  </div>

  <div v-else class="space-y-6">
    <fieldset v-for="[groupName, groupEntries] in groups" :key="groupName">
      <legend class="mb-3 text-sm font-semibold text-slate-300">{{ groupName }}</legend>
      <div class="space-y-3">
        <SettingField
          v-for="entry in groupEntries"
          :key="`${entry.definition.namespace}/${entry.definition.key}`"
          :entry="entry"
          :saving="savingKey === `${entry.definition.namespace}/${entry.definition.key}`"
          @save="(value: string) => handleSave(entry, value)"
          @reset="handleReset(entry)"
        />
      </div>
    </fieldset>
  </div>
</template>
