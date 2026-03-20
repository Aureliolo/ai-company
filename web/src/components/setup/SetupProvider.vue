<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import { useProviderStore } from '@/stores/providers'
import { useSetupStore } from '@/stores/setup'
import { getErrorMessage } from '@/utils/errors'
import type { ProviderPreset, TestConnectionResponse } from '@/api/types'

const emit = defineEmits<{
  next: []
  previous: []
}>()

const store = useProviderStore()
const setupStore = useSetupStore()

const selectedPreset = ref<ProviderPreset | null>(null)
const providerName = ref('')
const baseUrl = ref('')
const apiKey = ref('')
const error = ref<string | null>(null)
const creating = ref(false)
const testing = ref(false)
const discovering = ref(false)
const probing = ref(false)
const probeMessage = ref<string | null>(null)
const probedUrl = ref<string | null>(null)
let probeGeneration = 0
const createdProviderName = ref<string | null>(null)
const testPassed = ref(false)
const testResult = ref<TestConnectionResponse | null>(null)
/** Whether user is changing an existing provider. */
const changingProvider = ref(false)

const hasProviders = computed(() => Object.keys(store.providers).length > 0)

const createdProvider = computed(() => {
  if (!createdProviderName.value) return null
  return store.providers[createdProviderName.value] ?? null
})

const hasModels = computed(() => {
  if (!createdProvider.value) return false
  return createdProvider.value.models.length > 0
})

const canProceed = computed(() => hasProviders.value && hasModels.value && testPassed.value)

/** Whether to show the completed summary state. */
const showSummary = computed(() =>
  setupStore.isStepComplete('provider') && !changingProvider.value,
)

const isFormValid = computed(() => {
  if (probing.value) return false
  if (!selectedPreset.value) return false
  if (!providerName.value.trim()) return false
  if (
    selectedPreset.value.auth_type === 'api_key' &&
    !apiKey.value.trim()
  ) {
    return false
  }
  return true
})

// Clear stale probe banner when the user manually edits baseUrl.
watch(baseUrl, (val) => {
  if (!probeMessage.value) return
  if (probedUrl.value ? val !== probedUrl.value : val) {
    probeMessage.value = null
    probedUrl.value = null
  }
})

/** Guidance message when provider has no models. */
const noModelsGuidance = computed(() => {
  if (!selectedPreset.value && !createdProviderName.value) return null
  const preset = selectedPreset.value?.name
  if (preset === 'ollama') {
    return 'Make sure Ollama is running and you have pulled at least one model (e.g. ollama pull llama3.2).'
  }
  if (preset === 'lm-studio') {
    return 'Make sure LM Studio is running with at least one model loaded.'
  }
  if (preset === 'vllm') {
    return 'Make sure vLLM is running and serving a model.'
  }
  return 'No models detected. Make sure your provider is running and has models available.'
})

function authTypeLabel(authType: string): string {
  switch (authType) {
    case 'api_key': return 'API Key'
    case 'oauth': return 'OAuth'
    case 'custom_header': return 'Custom Header'
    case 'none': return 'No Auth'
    default: return authType
  }
}

function authTypeSeverity(authType: string): 'info' | 'warn' | 'success' | 'secondary' {
  switch (authType) {
    case 'api_key': return 'info'
    case 'oauth': return 'warn'
    case 'none': return 'success'
    default: return 'secondary'
  }
}

async function selectPreset(preset: ProviderPreset) {
  const myGen = ++probeGeneration
  selectedPreset.value = preset
  providerName.value = preset.name
  baseUrl.value = preset.default_base_url ?? ''
  apiKey.value = ''
  error.value = null
  createdProviderName.value = null
  testPassed.value = false
  testResult.value = null
  probeMessage.value = null
  probedUrl.value = null
  probing.value = false

  // Auto-probe candidate URLs for no-auth local presets.
  if (preset.auth_type === 'none' && preset.candidate_urls.length > 0) {
    probing.value = true
    try {
      const result = await store.probePreset(preset.name)
      if (myGen !== probeGeneration) return
      if (result.url) {
        probedUrl.value = result.url
        baseUrl.value = result.url
        const modelText = result.model_count > 0
          ? ` with ${result.model_count} model${result.model_count !== 1 ? 's' : ''}`
          : ''
        probeMessage.value = `Detected at ${result.url}${modelText}`
      } else {
        probeMessage.value = 'Not detected -- enter the URL manually'
      }
    } catch (err) {
      // Probe is best-effort; fall back to default URL.
      if (myGen === probeGeneration) {
        probeMessage.value = 'Auto-detection unavailable -- enter the URL manually'
      }
    } finally {
      if (myGen === probeGeneration) {
        probing.value = false
      }
    }
  }
}

function clearSelection() {
  selectedPreset.value = null
  providerName.value = ''
  baseUrl.value = ''
  apiKey.value = ''
  error.value = null
}

async function handleChangeProvider() {
  if (!createdProviderName.value) {
    changingProvider.value = true
    return
  }
  const nameToDelete = createdProviderName.value
  try {
    await store.deleteProvider(nameToDelete)
  } catch (err) {
    error.value = getErrorMessage(err)
    return
  }
  createdProviderName.value = null
  selectedPreset.value = null
  testPassed.value = false
  testResult.value = null
  error.value = null
  changingProvider.value = true
}

async function handleAddProvider() {
  if (!selectedPreset.value) return
  creating.value = true
  error.value = null
  try {
    await store.createFromPreset({
      preset_name: selectedPreset.value.name,
      name: providerName.value,
      ...(apiKey.value ? { api_key: apiKey.value } : {}),
      ...(baseUrl.value && baseUrl.value !== (selectedPreset.value.default_base_url ?? '')
        ? { base_url: baseUrl.value }
        : {}),
    })
    createdProviderName.value = providerName.value
    changingProvider.value = false

    // Always run model discovery after creation to ensure consistent
    // state. The backend auto-discovers during creation for no-auth
    // presets, but re-fetching ensures the store is up to date.
    await handleDiscoverModels()
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    creating.value = false
  }
}

async function handleDiscoverModels() {
  if (!createdProviderName.value) return
  discovering.value = true
  error.value = null
  try {
    await store.discoverModels(createdProviderName.value)
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    discovering.value = false
  }
}

async function handleTestConnection() {
  if (!createdProviderName.value) return
  testing.value = true
  error.value = null
  try {
    const res = await store.testConnection(createdProviderName.value)
    testResult.value = res
    testPassed.value = res.success
    if (!res.success) {
      error.value = res.error ?? 'Connection test failed'
    } else {
      error.value = null
    }
  } catch (err) {
    testResult.value = {
      success: false,
      latency_ms: null,
      error: getErrorMessage(err),
      model_tested: null,
    }
    testPassed.value = false
    error.value = getErrorMessage(err)
  } finally {
    testing.value = false
  }
}

onMounted(async () => {
  try {
    await Promise.all([store.fetchPresets(), store.fetchProviders()])
  } catch (err) {
    error.value = getErrorMessage(err)
  }
  if (hasProviders.value) {
    const names = Object.keys(store.providers)
    createdProviderName.value = names[0] ?? null
    // Auto-trigger connection test instead of silently auto-passing.
    if (hasModels.value) {
      await handleTestConnection()
    }
  }
})
</script>

<template>
  <div class="mx-auto w-full max-w-lg">
    <div class="mb-6 text-center">
      <h2 class="text-2xl font-semibold text-slate-100">Configure LLM Provider</h2>
      <p class="mt-1 text-sm text-slate-400">
        Connect an LLM provider so your agents can think and act.
      </p>
    </div>

    <!-- Completed summary state -->
    <template v-if="showSummary && createdProviderName && createdProvider">
      <div class="rounded-lg border border-green-500/20 bg-green-500/10 p-4">
        <div class="mb-3 flex items-center gap-2">
          <i class="pi pi-check-circle text-xl text-green-400" />
          <span class="text-sm font-medium text-green-300">Provider configured</span>
        </div>
        <div class="space-y-1 text-sm text-slate-300">
          <p>Name: <strong>{{ createdProviderName }}</strong></p>
          <p v-if="createdProvider.base_url">URL: {{ createdProvider.base_url }}</p>
          <p>Models: {{ createdProvider.models.length }} available</p>
          <p v-if="testPassed" class="text-green-400">
            <i class="pi pi-check-circle mr-1" />Connection tested
          </p>
        </div>
        <Button
          label="Change Provider"
          icon="pi pi-refresh"
          severity="secondary"
          size="small"
          outlined
          class="mt-3"
          @click="handleChangeProvider"
        />
      </div>
      <div class="mt-8 flex justify-between">
        <Button
          label="Back"
          icon="pi pi-arrow-left"
          severity="secondary"
          outlined
          @click="emit('previous')"
        />
        <Button
          label="Next"
          icon="pi pi-arrow-right"
          icon-pos="right"
          @click="emit('next')"
        />
      </div>
    </template>

    <!-- Active provider setup -->
    <template v-else>
      <!-- Already created state (within active setup, not summary) -->
      <div
        v-if="createdProviderName && !selectedPreset"
        class="mb-6 rounded-lg border border-green-500/20 bg-green-500/10 p-4 text-center"
      >
        <i class="pi pi-check-circle mb-2 text-2xl text-green-400" />
        <p class="text-sm text-green-300">
          Provider <strong>{{ createdProviderName }}</strong> is configured.
        </p>
      </div>

      <!-- Preset cards (show when no preset is selected and no provider created yet) -->
      <template v-if="!selectedPreset && !createdProviderName">
        <div class="grid grid-cols-2 gap-3">
          <button
            v-for="preset in store.presets"
            :key="preset.name"
            class="rounded-lg border border-slate-700 bg-slate-900 p-4 text-left transition-colors hover:border-brand-600 hover:bg-slate-800"
            @click="selectPreset(preset)"
          >
            <div class="mb-2 flex items-center justify-between">
              <span class="text-sm font-medium text-slate-100">{{ preset.display_name }}</span>
              <Tag
                :value="authTypeLabel(preset.auth_type)"
                :severity="authTypeSeverity(preset.auth_type)"
                class="text-[10px]"
              />
            </div>
            <p class="text-xs leading-relaxed text-slate-400">{{ preset.description }}</p>
          </button>
        </div>
      </template>

      <!-- Configuration form (after selecting a preset) -->
      <template v-if="selectedPreset && !createdProviderName">
        <div class="mb-4 flex items-center gap-2">
          <button
            class="text-sm text-slate-400 hover:text-slate-200"
            @click="clearSelection"
          >
            <i class="pi pi-arrow-left mr-1" />Back
          </button>
          <span class="text-sm text-slate-300">
            Configuring <strong>{{ selectedPreset.display_name }}</strong>
          </span>
        </div>

        <form class="space-y-4" @submit.prevent="handleAddProvider">
          <div>
            <label for="sp-name" class="mb-1 block text-sm text-slate-300">Provider Name</label>
            <InputText
              id="sp-name"
              v-model="providerName"
              class="w-full"
              placeholder="my-provider"
            />
          </div>

          <div>
            <label for="sp-base-url" class="mb-1 block text-sm text-slate-300">Base URL</label>
            <InputText
              id="sp-base-url"
              v-model="baseUrl"
              class="w-full"
              :disabled="probing"
              :placeholder="selectedPreset.default_base_url ?? 'https://api.example.com'"
            />
            <div v-if="probing" aria-live="polite" class="mt-1 flex items-center gap-2 text-xs text-slate-400">
              <i class="pi pi-spin pi-spinner" aria-hidden="true" />
              <span>Detecting provider...</span>
            </div>
            <div
              v-else-if="probeMessage"
              role="status"
              aria-live="polite"
              class="mt-1 text-xs"
              :class="probedUrl ? 'text-green-400' : 'text-amber-400'"
            >
              {{ probeMessage }}
            </div>
          </div>

          <div v-if="selectedPreset.auth_type === 'api_key'">
            <label for="sp-api-key" class="mb-1 block text-sm text-slate-300">API Key</label>
            <InputText
              id="sp-api-key"
              v-model="apiKey"
              type="password"
              class="w-full"
              placeholder="sk-..."
            />
          </div>

          <div
            v-if="error"
            role="alert"
            class="rounded bg-red-500/10 p-3 text-sm text-red-400"
          >
            {{ error }}
          </div>

          <Button
            type="submit"
            label="Add Provider"
            icon="pi pi-plus"
            class="w-full"
            :loading="creating"
            :disabled="!isFormValid"
          />
        </form>
      </template>

      <!-- Post-creation: discovery + test connection -->
      <template v-if="createdProviderName">
        <div class="mt-4 flex flex-col items-center gap-3">
          <!-- No models guidance -->
          <div
            v-if="!hasModels"
            class="w-full rounded-lg border border-amber-500/20 bg-amber-500/10 p-4"
          >
            <div class="mb-2 flex items-center gap-2">
              <i class="pi pi-exclamation-triangle text-amber-400" />
              <span class="text-sm font-medium text-amber-300">No models detected</span>
            </div>
            <p class="mb-3 text-xs leading-relaxed text-amber-200/80">
              {{ noModelsGuidance }}
            </p>
            <Button
              label="Retry Discovery"
              icon="pi pi-refresh"
              severity="warn"
              size="small"
              outlined
              :loading="discovering"
              @click="handleDiscoverModels"
            />
          </div>

          <!-- Models found indicator -->
          <div
            v-if="hasModels && createdProvider"
            class="w-full rounded-lg border border-green-500/20 bg-green-500/10 p-3 text-center"
          >
            <p class="text-sm text-green-300">
              <i class="pi pi-check-circle mr-1" />
              {{ createdProvider.models.length }} model{{ createdProvider.models.length !== 1 ? 's' : '' }} available
            </p>
          </div>

          <!-- Test connection (only show when models exist) -->
          <template v-if="hasModels">
            <div v-if="!testPassed" class="flex items-center gap-3">
              <Button
                label="Test Connection"
                icon="pi pi-bolt"
                severity="info"
                size="small"
                :loading="testing"
                @click="handleTestConnection"
              />
            </div>
            <div v-if="testResult" class="text-center">
              <p v-if="testResult.success" class="text-sm text-green-400">
                <i class="pi pi-check-circle mr-1" />
                Connection successful{{ testResult.latency_ms != null ? ` (${testResult.latency_ms}ms)` : '' }}
              </p>
              <p v-else class="text-sm text-red-400">
                <i class="pi pi-times-circle mr-1" />
                {{ testResult.error ?? 'Connection failed' }}
              </p>
            </div>
          </template>

          <!-- Change provider button -->
          <Button
            label="Change Provider"
            icon="pi pi-refresh"
            severity="secondary"
            size="small"
            text
            class="mt-2"
            @click="handleChangeProvider"
          />

          <div
            v-if="error && createdProviderName"
            role="alert"
            class="mt-2 w-full rounded bg-red-500/10 p-3 text-sm text-red-400"
          >
            {{ error }}
          </div>
        </div>
      </template>

      <!-- Navigation buttons -->
      <div class="mt-8 flex justify-between">
        <Button
          label="Back"
          icon="pi pi-arrow-left"
          severity="secondary"
          outlined
          @click="emit('previous')"
        />
        <Button
          label="Next"
          icon="pi pi-arrow-right"
          icon-pos="right"
          :disabled="!canProceed"
          @click="emit('next')"
        />
      </div>
    </template>
  </div>
</template>
