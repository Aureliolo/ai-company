<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import { useProviderStore } from '@/stores/providers'
import { getErrorMessage } from '@/utils/errors'
import type { ProviderPreset, TestConnectionResponse } from '@/api/types'

const emit = defineEmits<{
  next: []
}>()

const store = useProviderStore()

const selectedPreset = ref<ProviderPreset | null>(null)
const providerName = ref('')
const baseUrl = ref('')
const apiKey = ref('')
const error = ref<string | null>(null)
const creating = ref(false)
const testing = ref(false)
const createdProviderName = ref<string | null>(null)
const testPassed = ref(false)
const testResult = ref<TestConnectionResponse | null>(null)

const hasProviders = computed(() => Object.keys(store.providers).length > 0)

const canProceed = computed(() => hasProviders.value && testPassed.value)

const isFormValid = computed(() => {
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

function selectPreset(preset: ProviderPreset) {
  selectedPreset.value = preset
  providerName.value = preset.name
  baseUrl.value = preset.default_base_url ?? ''
  apiKey.value = ''
  error.value = null
  createdProviderName.value = null
  testPassed.value = false
  testResult.value = null
}

function clearSelection() {
  selectedPreset.value = null
  providerName.value = ''
  baseUrl.value = ''
  apiKey.value = ''
  error.value = null
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
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    creating.value = false
  }
}

async function handleTestComplete() {
  if (!createdProviderName.value) return
  testing.value = true
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
    testPassed.value = true
    const names = Object.keys(store.providers)
    createdProviderName.value = names[0] ?? null
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

    <!-- Already created state -->
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
            :placeholder="selectedPreset.default_base_url ?? 'https://api.example.com'"
          />
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

    <!-- Test connection (after provider is created) -->
    <template v-if="createdProviderName">
      <div class="mt-4 flex flex-col items-center gap-3">
        <div v-if="!testPassed" class="flex items-center gap-3">
          <Button
            label="Test Connection"
            icon="pi pi-bolt"
            severity="info"
            size="small"
            :loading="testing"
            @click="handleTestComplete"
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

        <div
          v-if="error && createdProviderName"
          role="alert"
          class="mt-2 w-full rounded bg-red-500/10 p-3 text-sm text-red-400"
        >
          {{ error }}
        </div>
      </div>
    </template>

    <!-- Next button -->
    <div class="mt-8 flex justify-end">
      <Button
        label="Next"
        icon="pi pi-arrow-right"
        icon-pos="right"
        :disabled="!canProceed"
        @click="emit('next')"
      />
    </div>
  </div>
</template>
