<script setup lang="ts">
import { useRouter } from 'vue-router'
import Button from 'primevue/button'

defineProps<{
  companyName: string
  agentName: string
  providerName: string
}>()

const router = useRouter()

function goToDashboard() {
  router.push('/')
}
</script>

<template>
  <div class="flex flex-col items-center text-center">
    <i class="pi pi-check-circle mb-4 text-5xl text-green-400" />
    <h2 class="mb-3 text-3xl font-semibold text-slate-100">Setup Complete!</h2>
    <p class="mb-6 max-w-md text-sm leading-relaxed text-slate-400">
      Your synthetic organization is ready to go. Here is what was created:
    </p>

    <div class="mb-8 w-full max-w-sm space-y-3">
      <div class="flex items-center justify-between rounded-lg border border-slate-700 bg-slate-900 px-4 py-3">
        <span class="text-xs text-slate-400">Company</span>
        <span class="text-sm font-medium text-slate-100">{{ companyName }}</span>
      </div>
      <div class="flex items-center justify-between rounded-lg border border-slate-700 bg-slate-900 px-4 py-3">
        <span class="text-xs text-slate-400">First Agent</span>
        <span class="text-sm font-medium text-slate-100">{{ agentName }}</span>
      </div>
      <div class="flex items-center justify-between rounded-lg border border-slate-700 bg-slate-900 px-4 py-3">
        <span class="text-xs text-slate-400">LLM Provider</span>
        <span class="text-sm font-medium text-slate-100">{{ providerName }}</span>
      </div>
    </div>

    <Button
      label="Go to Dashboard"
      icon="pi pi-home"
      @click="goToDashboard"
    />
  </div>
</template>
