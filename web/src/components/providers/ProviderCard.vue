<script setup lang="ts">
import { ref } from 'vue'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import ProviderTestButton from './ProviderTestButton.vue'
import type { ProviderConfig } from '@/api/types'

const props = defineProps<{
  name: string
  config: ProviderConfig
}>()

const emit = defineEmits<{
  edit: [name: string]
  delete: [name: string]
}>()

const confirmingDelete = ref(false)

function handleDelete() {
  if (!confirmingDelete.value) {
    confirmingDelete.value = true
    return
  }
  emit('delete', props.name)
  confirmingDelete.value = false
}

function cancelDelete() {
  confirmingDelete.value = false
}

function authBadgeSeverity(authType: string): 'success' | 'info' | 'warn' | 'secondary' {
  switch (authType) {
    case 'api_key': return 'info'
    case 'oauth': return 'warn'
    case 'custom_header': return 'secondary'
    case 'none': return 'success'
    default: return 'secondary'
  }
}
</script>

<template>
  <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-4 transition-colors hover:border-slate-600">
    <div class="mb-3 flex items-start justify-between">
      <div>
        <h3 class="text-base font-medium text-slate-200">{{ name }}</h3>
        <div class="mt-1 flex items-center gap-2">
          <Tag :value="config.driver" severity="info" class="text-xs" />
          <Tag :value="config.auth_type" :severity="authBadgeSeverity(config.auth_type)" class="text-xs" />
        </div>
      </div>
      <span class="text-xs text-slate-500">{{ config.models.length }} model{{ config.models.length !== 1 ? 's' : '' }}</span>
    </div>

    <div v-if="config.base_url" class="mb-3 truncate text-xs text-slate-400" :title="config.base_url">
      {{ config.base_url }}
    </div>

    <div class="mb-3 flex flex-wrap gap-1">
      <span
        v-for="model in config.models"
        :key="model.id"
        class="rounded bg-slate-700 px-1.5 py-0.5 text-xs text-slate-300"
      >
        {{ model.alias ?? model.id }}
      </span>
    </div>

    <div class="flex items-center gap-2">
      <ProviderTestButton :provider-name="name" />
      <Button
        label="Edit"
        size="small"
        severity="secondary"
        text
        @click="emit('edit', name)"
      />
      <template v-if="!confirmingDelete">
        <Button
          label="Delete"
          size="small"
          severity="danger"
          text
          @click="handleDelete"
        />
      </template>
      <template v-else>
        <Button
          label="Confirm"
          size="small"
          severity="danger"
          @click="handleDelete"
        />
        <Button
          label="Cancel"
          size="small"
          severity="secondary"
          text
          @click="cancelDelete"
        />
      </template>
    </div>
  </div>
</template>
