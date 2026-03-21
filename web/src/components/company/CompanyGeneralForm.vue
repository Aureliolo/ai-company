<script setup lang="ts">
import { computed } from 'vue'
import SettingField from '@/components/settings/SettingField.vue'
import type { SettingEntry, SettingNamespace } from '@/api/types'

const props = defineProps<{
  entries: SettingEntry[]
  savingKey?: string | null
}>()

const emit = defineEmits<{
  save: [entry: SettingEntry, value: string]
  reset: [entry: SettingEntry]
  dirty: [payload: { namespace: SettingNamespace; key: string; value: string; isDirty: boolean }]
}>()

/** General company settings (exclude agents and departments). */
const generalEntries = computed(() =>
  props.entries.filter((e) =>
    e.definition.key !== 'agents' && e.definition.key !== 'departments',
  ),
)
</script>

<template>
  <div
    v-if="generalEntries.length === 0"
    class="rounded-lg border border-dashed border-slate-700 p-8 text-center"
  >
    <p class="text-sm text-slate-400">No general company settings available.</p>
  </div>
  <div v-else class="grid grid-cols-1 gap-4 xl:grid-cols-2">
    <SettingField
      v-for="entry in generalEntries"
      :key="entry.definition.key"
      :entry="entry"
      :saving="savingKey === `${entry.definition.namespace}/${entry.definition.key}`"
      @save="(value: string) => emit('save', entry, value)"
      @reset="emit('reset', entry)"
      @dirty="emit('dirty', $event)"
    />
  </div>
</template>
