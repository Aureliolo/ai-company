<script setup lang="ts">
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import type { AgentConfigEntry } from '@/api/types'

defineProps<{
  agent: AgentConfigEntry
  index: number
}>()

defineEmits<{
  edit: [index: number]
  delete: [index: number]
}>()

type TagSeverity = 'info' | 'success' | 'warn' | 'danger' | 'secondary' | 'contrast'

const levelColors: Record<string, TagSeverity> = {
  junior: 'info',
  mid: 'info',
  senior: 'success',
  lead: 'warn',
  principal: 'warn',
  director: 'danger',
  vp: 'danger',
  c_suite: 'danger',
}
</script>

<template>
  <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
    <div class="mb-2 flex items-start justify-between">
      <div>
        <h4 class="text-sm font-medium text-slate-200">
          {{ agent.name }}
        </h4>
        <p class="text-xs text-slate-400">
          {{ agent.role }}
        </p>
      </div>
      <div class="flex gap-1">
        <Button
          icon="pi pi-pencil"
          text
          rounded
          size="small"
          severity="secondary"
          aria-label="Edit agent"
          @click="$emit('edit', index)"
        />
        <Button
          icon="pi pi-trash"
          text
          rounded
          size="small"
          severity="danger"
          aria-label="Delete agent"
          @click="$emit('delete', index)"
        />
      </div>
    </div>

    <div class="flex flex-wrap gap-1.5">
      <Tag
        :value="agent.department"
        severity="secondary"
      />
      <Tag
        :value="agent.level"
        :severity="levelColors[agent.level] ?? 'info'"
      />
      <Tag
        v-if="agent.autonomy_level"
        :value="agent.autonomy_level"
        severity="warn"
      />
    </div>
  </div>
</template>
