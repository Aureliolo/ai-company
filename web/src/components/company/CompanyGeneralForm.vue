<script setup lang="ts">
import { computed } from 'vue'
import SettingGroupRenderer from '@/components/settings/SettingGroupRenderer.vue'
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
  <div v-else class="space-y-2">
    <p class="text-sm text-slate-400">
      Core company identity and operational defaults.
    </p>
    <SettingGroupRenderer
      :entries="generalEntries"
      :show-advanced="true"
      :saving-key="savingKey"
      @save="(entry: SettingEntry, value: string) => emit('save', entry, value)"
      @reset="(entry: SettingEntry) => emit('reset', entry)"
      @dirty="emit('dirty', $event)"
    />
  </div>
</template>
