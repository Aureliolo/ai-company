<script setup lang="ts">
import Button from 'primevue/button'
import { useWebSocketStore } from '@/stores/websocket'

const wsStore = useWebSocketStore()

function reload() {
  window.location.reload()
}
</script>

<template>
  <div
    v-if="wsStore.reconnectExhausted"
    role="alert"
    class="flex items-center gap-3 border-b border-amber-500/20 bg-amber-500/10 px-4 py-2.5"
  >
    <i class="pi pi-exclamation-triangle text-amber-400" aria-hidden="true" />
    <span class="flex-1 text-sm text-amber-300">
      Connection lost -- real-time updates unavailable.
    </span>
    <Button
      label="Reload"
      icon="pi pi-refresh"
      severity="warn"
      size="small"
      text
      @click="reload"
    />
  </div>
</template>
