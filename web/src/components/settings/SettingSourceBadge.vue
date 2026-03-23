<script setup lang="ts">
import Tag from 'primevue/tag'
import type { SettingSource } from '@/api/types'

defineProps<{
  source: SettingSource
}>()

const SOURCE_LABELS: Record<SettingSource, string> = {
  db: 'Custom',
  env: 'Environment',
  yaml: 'Config File',
  default: 'Default',
}

const SOURCE_SEVERITY: Record<SettingSource, string> = {
  db: 'info',
  env: 'warn',
  yaml: 'secondary',
  default: 'contrast',
}
</script>

<template>
  <Tag
    :value="SOURCE_LABELS[source]"
    :severity="SOURCE_SEVERITY[source]"
  />
</template>
