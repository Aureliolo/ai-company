<script setup lang="ts">
defineProps<{
  visible: boolean
}>()
</script>

<template>
  <div
    v-if="visible"
    role="status"
    class="rounded-lg border-l-4 border-l-amber-500 bg-amber-500/10 px-4 py-3"
  >
    <div class="flex items-center gap-2">
      <i
        class="pi pi-exclamation-triangle text-amber-400"
        aria-hidden="true"
      />
      <p class="text-sm text-amber-300">
        Advanced mode is active -- these settings can affect system stability and security.
      </p>
    </div>
  </div>
</template>
