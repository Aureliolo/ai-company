<script setup lang="ts">
import { ref } from 'vue'
import Button from 'primevue/button'
import { useProviderStore } from '@/stores/providers'
import type { TestConnectionResponse } from '@/api/types'

const props = defineProps<{
  providerName: string
}>()

const store = useProviderStore()
const testing = ref(false)
const result = ref<TestConnectionResponse | null>(null)
let clearTimer: ReturnType<typeof setTimeout> | null = null

async function handleTest() {
  testing.value = true
  result.value = null
  if (clearTimer) {
    clearTimeout(clearTimer)
    clearTimer = null
  }

  try {
    result.value = await store.testConnection(props.providerName)
  } catch {
    result.value = {
      success: false,
      latency_ms: null,
      error: 'Request failed',
      model_tested: null,
    }
  } finally {
    testing.value = false
  }

  clearTimer = setTimeout(() => {
    result.value = null
    clearTimer = null
  }, 10_000)
}
</script>

<template>
  <div class="flex items-center gap-2">
    <Button
      label="Test"
      size="small"
      severity="info"
      text
      :loading="testing"
      @click="handleTest"
    />
    <template v-if="result">
      <span v-if="result.success" class="text-xs text-green-400">
        {{ result.latency_ms != null ? `${result.latency_ms}ms` : 'OK' }}
      </span>
      <span v-else class="max-w-[200px] truncate text-xs text-red-400" :title="result.error ?? undefined">
        {{ result.error ?? 'Failed' }}
      </span>
    </template>
  </div>
</template>
