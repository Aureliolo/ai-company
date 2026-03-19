<script setup lang="ts">
import Button from 'primevue/button'

const emit = defineEmits<{
  next: []
}>()
</script>

<template>
  <div class="flex flex-col items-center text-center">
    <div
      class="mb-6 flex h-16 w-16 items-center justify-center rounded-xl bg-brand-600 text-2xl font-bold text-white"
    >
      S
    </div>
    <h2 class="mb-3 text-3xl font-semibold text-slate-100">Welcome to SynthOrg</h2>
    <p class="mb-2 max-w-md text-sm leading-relaxed text-slate-400">
      SynthOrg lets you build a synthetic organization -- autonomous AI agents
      orchestrated as a virtual company, complete with roles, departments, and workflows.
    </p>
    <p class="mb-8 max-w-md text-sm leading-relaxed text-slate-400">
      This wizard will walk you through creating an admin account, configuring an LLM
      provider, setting up your company, and hiring your first agent.
    </p>
    <Button
      label="Get Started"
      icon="pi pi-arrow-right"
      icon-pos="right"
      @click="emit('next')"
    />
  </div>
</template>
