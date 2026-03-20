<script setup lang="ts">
import { ref, computed, watch, onMounted, type Ref } from 'vue'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Button from 'primevue/button'
import { useProviderStore } from '@/stores/providers'
import { useSetupStore } from '@/stores/setup'
import * as setupApi from '@/api/endpoints/setup'
import { getErrorMessage } from '@/utils/errors'
import type { SeniorityLevel, SetupAgentResponse } from '@/api/types'

const emit = defineEmits<{
  complete: [agentName: string, providerName: string]
  previous: []
}>()

const providerStore = useProviderStore()
const setupStore = useSetupStore()

const ROLE_OPTIONS = [
  { label: 'CEO', value: 'CEO' },
  { label: 'CTO', value: 'CTO' },
  { label: 'Backend Developer', value: 'Backend Developer' },
  { label: 'Full-Stack Developer', value: 'Full-Stack Developer' },
  { label: 'QA Engineer', value: 'QA Engineer' },
  { label: 'Product Manager', value: 'Product Manager' },
  { label: 'Designer', value: 'Designer' },
]

const PERSONALITY_PRESETS = [
  { label: 'Visionary Leader', value: 'visionary_leader' },
  { label: 'Pragmatic Builder', value: 'pragmatic_builder' },
  { label: 'Methodical Analyst', value: 'methodical_analyst' },
  { label: 'Creative Innovator', value: 'creative_innovator' },
  { label: 'Eager Learner', value: 'eager_learner' },
]

const ROLE_LEVELS: Record<string, SeniorityLevel> = {
  CEO: 'c_suite',
  CTO: 'c_suite',
  'Backend Developer': 'mid',
  'Full-Stack Developer': 'mid',
  'QA Engineer': 'mid',
  'Product Manager': 'senior',
  Designer: 'mid',
}

const ROLE_DEPARTMENTS: Record<string, string> = {
  CEO: 'executive',
  CTO: 'executive',
  'Backend Developer': 'engineering',
  'Full-Stack Developer': 'engineering',
  'QA Engineer': 'quality_assurance',
  'Product Manager': 'product',
  Designer: 'design',
}

const agentName = ref('')
const selectedRole = ref<string | null>(null)
const selectedProvider = ref<string | null>(null)
const selectedModel = ref<string | null>(null)
const selectedPersonality = ref<string | null>(null)
const error = ref<string | null>(null)
const creating = ref(false)
// Cached agent creation result so markComplete retries skip re-creation.
// Component-scoped ref prevents leaking across mounts.
const savedAgent: Ref<SetupAgentResponse | null> = ref(null)
/** Whether user clicked Edit on the completed summary. */
const editing = ref(false)

/** All models across all configured providers, with provider name prefix. */
const modelOptions = computed(() => {
  const options: { label: string; value: string; provider: string }[] = []
  for (const [name, config] of Object.entries(providerStore.providers)) {
    for (const model of config.models) {
      options.push({
        label: model.alias ? `${model.alias} (${name})` : `${model.id} (${name})`,
        value: `${name}::${model.id}`,
        provider: name,
      })
    }
  }
  return options
})

const providerOptions = computed(() =>
  Object.keys(providerStore.providers).map((name) => ({
    label: name,
    value: name,
  })),
)

/** Models filtered by selected provider. */
const filteredModels = computed(() => {
  if (!selectedProvider.value) return modelOptions.value
  return modelOptions.value.filter((m) => m.provider === selectedProvider.value)
})

const isValid = computed(
  () =>
    agentName.value.trim().length > 0 &&
    selectedRole.value !== null &&
    selectedModel.value !== null &&
    selectedPersonality.value !== null,
)

/** Whether to show the completed summary. */
const showSummary = computed(() =>
  setupStore.isStepComplete('agent') && !editing.value && savedAgent.value !== null,
)

watch(selectedRole, (newRole) => {
  if (newRole && !agentName.value.trim()) {
    const roleSlug = newRole.replace(/\s+/g, '-').toLowerCase()
    agentName.value = `agent-${roleSlug}-001`
  }
})

// Clear model selection when provider changes so the form never submits
// a model that is no longer visible in the filtered dropdown.
watch(selectedProvider, () => {
  selectedModel.value = null
})

function startEditing() {
  if (savedAgent.value) {
    agentName.value = savedAgent.value.name
    selectedRole.value = savedAgent.value.role
    selectedModel.value = `${savedAgent.value.model_provider}::${savedAgent.value.model_id}`
  }
  editing.value = true
}

async function handleCreate() {
  if (creating.value) return
  if (!isValid.value || !selectedRole.value || !selectedModel.value || !selectedPersonality.value) {
    return
  }
  creating.value = true
  error.value = null

  // Parse "provider::model_id" format
  const [provider, ...modelParts] = selectedModel.value.split('::')
  const modelId = modelParts.join('::')

  try {
    // Create the agent first; store the result so a markComplete retry
    // does not re-create the agent (non-idempotent).
    const result = savedAgent.value ?? await setupApi.createAgent({
      name: agentName.value.trim(),
      role: selectedRole.value,
      level: ROLE_LEVELS[selectedRole.value] ?? 'mid',
      personality_preset: selectedPersonality.value,
      model_provider: provider,
      model_id: modelId,
      department: ROLE_DEPARTMENTS[selectedRole.value] ?? 'engineering',
      budget_limit_monthly: null,
    })
    savedAgent.value = result
    editing.value = false

    await setupStore.markComplete()
    emit('complete', result.name, result.model_provider)
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    creating.value = false
  }
}

onMounted(async () => {
  try {
    await providerStore.fetchProviders()
  } catch (err) {
    error.value = getErrorMessage(err)
  }
})
</script>

<template>
  <div class="mx-auto w-full max-w-sm">
    <div class="mb-6 text-center">
      <h2 class="text-2xl font-semibold text-slate-100">Hire Your First Agent</h2>
      <p class="mt-1 text-sm text-slate-400">
        Create the first AI agent for your organization.
      </p>
    </div>

    <!-- Completed summary -->
    <template v-if="showSummary && savedAgent">
      <div class="rounded-lg border border-green-500/20 bg-green-500/10 p-4">
        <div class="mb-3 flex items-center gap-2">
          <i class="pi pi-check-circle text-xl text-green-400" />
          <span class="text-sm font-medium text-green-300">Agent created</span>
        </div>
        <div class="space-y-1 text-sm text-slate-300">
          <p>Name: <strong>{{ savedAgent.name }}</strong></p>
          <p>Role: {{ savedAgent.role }}</p>
          <p>Department: {{ savedAgent.department }}</p>
          <p>Provider: {{ savedAgent.model_provider }}</p>
          <p>Model: {{ savedAgent.model_id }}</p>
        </div>
        <Button
          label="Edit"
          icon="pi pi-pencil"
          severity="secondary"
          size="small"
          outlined
          class="mt-3"
          @click="startEditing"
        />
      </div>
      <div class="mt-8 flex items-center gap-3">
        <Button
          type="button"
          label="Back"
          icon="pi pi-arrow-left"
          severity="secondary"
          outlined
          @click="emit('previous')"
        />
        <Button
          label="Finish Setup"
          icon="pi pi-check"
          class="flex-1"
          @click="emit('complete', savedAgent.name, savedAgent.model_provider)"
        />
      </div>
    </template>

    <!-- Creation/edit form -->
    <template v-else>
      <form class="space-y-4" @submit.prevent="handleCreate">
        <div>
          <label for="sa-role" class="mb-1 block text-sm text-slate-300">Role</label>
          <Select
            v-model="selectedRole"
            input-id="sa-role"
            :options="ROLE_OPTIONS"
            option-label="label"
            option-value="value"
            placeholder="Select a role..."
            class="w-full"
          />
        </div>

        <div>
          <label for="sa-name" class="mb-1 block text-sm text-slate-300">Agent Name</label>
          <InputText
            id="sa-name"
            v-model="agentName"
            class="w-full"
            placeholder="e.g. agent-ceo-001"
          />
        </div>

        <div>
          <label for="sa-provider" class="mb-1 block text-sm text-slate-300">Provider</label>
          <Select
            v-model="selectedProvider"
            input-id="sa-provider"
            :options="providerOptions"
            option-label="label"
            option-value="value"
            placeholder="All providers"
            class="w-full"
            show-clear
          />
        </div>

        <div>
          <label for="sa-model" class="mb-1 block text-sm text-slate-300">Model</label>
          <Select
            v-model="selectedModel"
            input-id="sa-model"
            :options="filteredModels"
            option-label="label"
            option-value="value"
            placeholder="Select a model..."
            class="w-full"
          />
        </div>

        <div>
          <label for="sa-personality" class="mb-1 block text-sm text-slate-300">Personality</label>
          <Select
            v-model="selectedPersonality"
            input-id="sa-personality"
            :options="PERSONALITY_PRESETS"
            option-label="label"
            option-value="value"
            placeholder="Select a personality..."
            class="w-full"
          />
        </div>

        <div
          v-if="error"
          role="alert"
          class="rounded bg-red-500/10 p-3 text-sm text-red-400"
        >
          {{ error }}
        </div>

        <div class="flex items-center gap-3">
          <Button
            type="button"
            label="Back"
            icon="pi pi-arrow-left"
            severity="secondary"
            outlined
            :disabled="creating"
            @click="emit('previous')"
          />
          <Button
            type="submit"
            label="Create Agent & Finish"
            icon="pi pi-user-plus"
            class="flex-1"
            :loading="creating"
            :disabled="!isValid || creating"
          />
        </div>
      </form>
    </template>
  </div>
</template>
