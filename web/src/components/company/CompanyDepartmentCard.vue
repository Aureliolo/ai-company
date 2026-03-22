<script setup lang="ts">
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import type { DepartmentEntry } from '@/api/types'

defineProps<{
  department: DepartmentEntry
  index: number
}>()

defineEmits<{
  edit: [index: number]
  delete: [index: number]
}>()
</script>

<template>
  <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
    <div class="mb-2 flex items-start justify-between">
      <div>
        <h4 class="text-sm font-medium text-slate-200">{{ department.name }}</h4>
        <p v-if="department.head" class="text-xs text-slate-400">Head: {{ department.head }}</p>
      </div>
      <div class="flex gap-1">
        <Button
          icon="pi pi-pencil"
          outlined
          rounded
          size="small"
          severity="secondary"
          aria-label="Edit department"
          @click="$emit('edit', index)"
        />
        <Button
          icon="pi pi-trash"
          outlined
          rounded
          size="small"
          severity="danger"
          aria-label="Delete department"
          @click="$emit('delete', index)"
        />
      </div>
    </div>

    <div class="flex flex-wrap gap-1.5">
      <Tag
        v-if="department.budget_percent !== undefined"
        :value="`${department.budget_percent}% budget`"
        severity="info"
      />
      <Tag
        v-if="department.teams?.length"
        :value="`${department.teams.length} team(s)`"
        severity="secondary"
      />
      <Tag v-if="department.autonomy_level" :value="department.autonomy_level" severity="warn" />
    </div>
  </div>
</template>
