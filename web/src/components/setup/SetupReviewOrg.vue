<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import Button from 'primevue/button'
import Select from 'primevue/select'
import InputText from 'primevue/inputtext'
import { useSetupStore } from '@/stores/setup'
import { useProviderStore } from '@/stores/providers'
import * as setupApi from '@/api/endpoints/setup'
import { getErrorMessage } from '@/utils/errors'
import type { SetupAgentSummary } from '@/api/types'

const emit = defineEmits<{
  complete: [providerName: string]
  previous: []
}>()

const setup = useSetupStore()
const providerStore = useProviderStore()

const error = ref<string | null>(null)
const completing = ref(false)

/** Whether we are in "add agent" mode (for Start Blank path). */
const showAddAgent = ref(false)
const newAgentRole = ref('')
const newAgentName = ref('')
const newAgentProvider = ref('')
const newAgentModel = ref('')
const addingAgent = ref(false)

// Reset model selection when the provider changes to prevent
// submitting an invalid provider/model pair.
watch(newAgentProvider, () => {
  newAgentModel.value = ''
})

const hasAgents = computed(() => setup.agents.length > 0)

const providerOptions = computed(() =>
  Object.keys(providerStore.providers).map((name) => ({
    label: name,
    value: name,
  })),
)

function modelOptionsForProvider(providerName: string) {
  const provider = providerStore.providers[providerName]
  if (!provider?.models) return []
  return provider.models.map((m: { id: string }) => ({
    label: m.id,
    value: m.id,
  }))
}

/** All models from all providers, flattened for the per-agent dropdowns. */
const allModelOptions = computed(() => {
  const options: { label: string; value: string; provider: string; modelId: string }[] = []
  for (const [pname, pcfg] of Object.entries(providerStore.providers)) {
    if (!pcfg.models) continue
    for (const m of pcfg.models) {
      options.push({
        label: `${pname} / ${m.id}`,
        value: JSON.stringify({ provider: pname, modelId: m.id }),
        provider: pname,
        modelId: m.id,
      })
    }
  }
  return options
})

function currentModelValue(agent: SetupAgentSummary): string {
  if (!agent.model_provider || !agent.model_id) return ''
  return JSON.stringify({ provider: agent.model_provider, modelId: agent.model_id })
}

async function handleModelChange(index: number, value: string) {
  let parsed: { provider: string; modelId: string }
  try {
    parsed = JSON.parse(value)
  } catch {
    return
  }
  if (!parsed.provider || !parsed.modelId) return
  error.value = null
  await setup.updateAgentModel(index, parsed.provider, parsed.modelId)
  if (setup.error) {
    error.value = setup.error
  }
}

function tierBadgeClass(tier: string): string {
  switch (tier) {
    case 'large':
      return 'bg-purple-500/20 text-purple-300'
    case 'small':
      return 'bg-green-500/20 text-green-300'
    default:
      return 'bg-blue-500/20 text-blue-300'
  }
}

async function handleAddAgent() {
  if (!newAgentRole.value.trim() || addingAgent.value) return
  addingAgent.value = true
  error.value = null
  try {
    await setupApi.createAgent({
      name: newAgentName.value.trim() || newAgentRole.value.trim(),
      role: newAgentRole.value.trim(),
      level: 'mid',
      personality_preset: 'pragmatic_builder',
      model_provider: newAgentProvider.value,
      model_id: newAgentModel.value,
      department: 'engineering',
      budget_limit_monthly: null,
    })
  } catch (err) {
    error.value = getErrorMessage(err)
    addingAgent.value = false
    return
  }
  // Create succeeded -- refresh the agents list. A refresh failure
  // should not revert the successful create, so use a separate block.
  try {
    await setup.fetchAgents()
  } catch (refreshErr) {
    error.value = `Agent created, but list refresh failed: ${getErrorMessage(refreshErr)}`
  }
  showAddAgent.value = false
  newAgentRole.value = ''
  newAgentName.value = ''
  newAgentProvider.value = ''
  newAgentModel.value = ''
  addingAgent.value = false
}

async function handleComplete() {
  if (completing.value) return
  completing.value = true
  error.value = null
  try {
    await setup.markComplete()
    const firstProvider = Object.keys(providerStore.providers)[0] ?? ''
    emit('complete', firstProvider)
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    completing.value = false
  }
}

onMounted(async () => {
  try {
    await providerStore.fetchProviders()
    // Load agents if the store cache is empty (e.g. on page refresh).
    if (setup.agents.length === 0) {
      await setup.fetchAgents()
    }
  } catch (err) {
    error.value = getErrorMessage(err)
  }
})
</script>

<template>
  <div class="mx-auto w-full max-w-lg">
    <div class="mb-6 text-center">
      <h2 class="text-2xl font-semibold text-slate-100">Review Your Organization</h2>
      <p class="mt-1 text-sm text-slate-400">
        Review the agents in your organization and adjust model assignments.
      </p>
    </div>

    <!-- Error -->
    <div
      v-if="error"
      role="alert"
      class="mb-4 rounded bg-red-500/10 p-3 text-center text-sm text-red-400"
    >
      {{ error }}
    </div>

    <!-- Agent list -->
    <div v-if="hasAgents" class="mb-6 space-y-3">
      <div
        v-for="(agent, index) in setup.agents"
        :key="agent.name || `${agent.role}-${index}`"
        class="rounded-lg border border-slate-700 bg-slate-900 p-4"
      >
        <div class="mb-2 flex items-center justify-between">
          <div>
            <span class="font-medium text-slate-100">{{ agent.name }}</span>
            <span class="ml-2 text-xs text-slate-400">{{ agent.role }}</span>
          </div>
          <span
            class="rounded-full px-2 py-0.5 text-xs font-medium"
            :class="tierBadgeClass(agent.tier)"
          >
            {{ agent.tier }}
          </span>
        </div>
        <div class="mb-2 text-xs text-slate-500">
          {{ agent.department }} &middot; {{ agent.level }}
        </div>
        <Select
          :model-value="currentModelValue(agent)"
          :options="allModelOptions"
          option-label="label"
          option-value="value"
          placeholder="Select model..."
          :aria-label="`Model for ${agent.name}`"
          class="w-full"
          @update:model-value="handleModelChange(index, $event)"
        />
      </div>
    </div>

    <!-- Empty state (Start Blank) -->
    <div v-else class="mb-6 text-center">
      <p class="mb-4 text-sm text-slate-400">
        No agents yet. Add at least one agent to get started.
      </p>
    </div>

    <!-- Add agent form (for blank path) -->
    <div v-if="showAddAgent" class="mb-6 rounded-lg border border-slate-700 bg-slate-900 p-4">
      <h3 class="mb-3 text-sm font-medium text-slate-200">Add Agent</h3>
      <div class="space-y-3">
        <InputText
          v-model="newAgentRole"
          placeholder="Role (e.g. Backend Developer)"
          aria-label="Agent role"
          class="w-full"
        />
        <InputText
          v-model="newAgentName"
          placeholder="Name (optional)"
          aria-label="Agent name"
          class="w-full"
        />
        <Select
          v-model="newAgentProvider"
          :options="providerOptions"
          option-label="label"
          option-value="value"
          placeholder="Provider"
          aria-label="Agent provider"
          class="w-full"
        />
        <Select
          v-if="newAgentProvider"
          v-model="newAgentModel"
          :options="modelOptionsForProvider(newAgentProvider)"
          option-label="label"
          option-value="value"
          placeholder="Model"
          aria-label="Agent model"
          class="w-full"
        />
        <div class="flex gap-2">
          <Button
            label="Add"
            size="small"
            :loading="addingAgent"
            :disabled="!newAgentRole.trim() || !newAgentProvider || !newAgentModel"
            @click="handleAddAgent"
          />
          <Button
            label="Cancel"
            size="small"
            severity="secondary"
            @click="showAddAgent = false"
          />
        </div>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex items-center justify-between">
      <Button
        label="Back"
        severity="secondary"
        icon="pi pi-arrow-left"
        @click="$emit('previous')"
      />
      <div class="flex gap-2">
        <Button
          v-if="!showAddAgent"
          label="Add Agent"
          severity="secondary"
          icon="pi pi-plus"
          size="small"
          @click="showAddAgent = true"
        />
        <Button
          label="Complete Setup"
          icon="pi pi-check"
          :loading="completing"
          :disabled="!hasAgents"
          @click="handleComplete"
        />
      </div>
    </div>
  </div>
</template>
