<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Button from 'primevue/button'
import { useProviderStore } from '@/stores/providers'
import type {
  AuthType,
  CreateFromPresetRequest,
  CreateProviderRequest,
  ProviderConfig,
  ProviderPreset,
  UpdateProviderRequest,
} from '@/api/types'

const props = defineProps<{
  visible: boolean
  mode: 'create' | 'edit'
  providerName?: string
  providerConfig?: ProviderConfig
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  save: [data: CreateProviderRequest | UpdateProviderRequest]
  savePreset: [data: CreateFromPresetRequest]
}>()

const store = useProviderStore()

const AUTH_TYPE_OPTIONS: { label: string; value: AuthType }[] = [
  { label: 'API Key', value: 'api_key' },
  { label: 'OAuth', value: 'oauth' },
  { label: 'Custom Header', value: 'custom_header' },
  { label: 'None', value: 'none' },
]

const name = ref('')
const driver = ref('litellm')
const authType = ref<AuthType>('api_key')
const baseUrl = ref('')
const apiKey = ref('')
const oauthTokenUrl = ref('')
const oauthClientId = ref('')
const oauthClientSecret = ref('')
const oauthScope = ref('')
const customHeaderName = ref('')
const customHeaderValue = ref('')
const selectedPreset = ref<ProviderPreset | null>(null)

watch(() => props.visible, (v) => {
  if (!v) return
  if (props.mode === 'edit' && props.providerConfig) {
    name.value = props.providerName ?? ''
    driver.value = props.providerConfig.driver
    authType.value = props.providerConfig.auth_type
    baseUrl.value = props.providerConfig.base_url ?? ''
    apiKey.value = ''
    oauthTokenUrl.value = props.providerConfig.oauth_token_url ?? ''
    oauthClientId.value = props.providerConfig.oauth_client_id ?? ''
    oauthClientSecret.value = ''
    oauthScope.value = props.providerConfig.oauth_scope ?? ''
    customHeaderName.value = props.providerConfig.custom_header_name ?? ''
    customHeaderValue.value = ''
  } else {
    name.value = ''
    driver.value = 'litellm'
    authType.value = 'api_key'
    baseUrl.value = ''
    apiKey.value = ''
    oauthTokenUrl.value = ''
    oauthClientId.value = ''
    oauthClientSecret.value = ''
    oauthScope.value = ''
    customHeaderName.value = ''
    customHeaderValue.value = ''
    selectedPreset.value = null
  }
})

watch(selectedPreset, (preset) => {
  if (!preset) return
  driver.value = preset.driver
  authType.value = preset.auth_type
  baseUrl.value = preset.default_base_url ?? ''
  // Only set name if the user hasn't typed one yet
  if (!name.value) {
    name.value = preset.name
  }
})

const isEditing = computed(() => props.mode === 'edit')

const isValid = computed(() => {
  if (props.mode === 'create' && !name.value.trim()) return false
  if (!driver.value.trim()) return false
  if (authType.value === 'oauth') {
    if (!oauthTokenUrl.value.trim() || !oauthClientId.value.trim()) return false
    // In create mode, secret is required; in edit mode, empty means "keep existing"
    if (!isEditing.value && !oauthClientSecret.value.trim()) return false
  }
  if (authType.value === 'custom_header') {
    if (!customHeaderName.value.trim()) return false
    // In create mode, secret is required; in edit mode, empty means "keep existing"
    if (!isEditing.value && !customHeaderValue.value.trim()) return false
  }
  return true
})

function handleSave() {
  if (props.mode === 'create') {
    // Use preset flow when a preset was selected
    if (selectedPreset.value) {
      const data: CreateFromPresetRequest = {
        preset_name: selectedPreset.value.name,
        name: name.value,
      }
      if (apiKey.value) data.api_key = apiKey.value
      if (baseUrl.value && baseUrl.value !== (selectedPreset.value.default_base_url ?? '')) {
        data.base_url = baseUrl.value
      }
      emit('savePreset', data)
      return
    }

    const data: CreateProviderRequest = {
      name: name.value,
      driver: driver.value,
      auth_type: authType.value,
    }
    if (baseUrl.value) data.base_url = baseUrl.value
    // Only include fields relevant to the active auth type
    if (authType.value === 'api_key' || authType.value === 'oauth') {
      if (apiKey.value) data.api_key = apiKey.value
    }
    if (authType.value === 'oauth') {
      if (oauthTokenUrl.value) data.oauth_token_url = oauthTokenUrl.value
      if (oauthClientId.value) data.oauth_client_id = oauthClientId.value
      if (oauthClientSecret.value) data.oauth_client_secret = oauthClientSecret.value
      if (oauthScope.value) data.oauth_scope = oauthScope.value
    }
    if (authType.value === 'custom_header') {
      if (customHeaderName.value) data.custom_header_name = customHeaderName.value
      if (customHeaderValue.value) data.custom_header_value = customHeaderValue.value
    }
    emit('save', data)
  } else {
    const data: UpdateProviderRequest = {}
    const prev = props.providerConfig
    if (driver.value !== prev?.driver) data.driver = driver.value
    if (authType.value !== prev?.auth_type) data.auth_type = authType.value
    if (baseUrl.value !== (prev?.base_url ?? '')) {
      data.base_url = baseUrl.value === '' ? null : baseUrl.value
    }

    // Include fields for the active auth type only
    if (authType.value === 'api_key' || authType.value === 'oauth') {
      if (apiKey.value) data.api_key = apiKey.value
    }
    if (authType.value === 'oauth') {
      if (oauthTokenUrl.value !== (prev?.oauth_token_url ?? '')) {
        data.oauth_token_url = oauthTokenUrl.value || null
      }
      if (oauthClientId.value !== (prev?.oauth_client_id ?? '')) {
        data.oauth_client_id = oauthClientId.value || null
      }
      if (oauthClientSecret.value) data.oauth_client_secret = oauthClientSecret.value
      if (oauthScope.value !== (prev?.oauth_scope ?? '')) {
        data.oauth_scope = oauthScope.value || null
      }
    }
    if (authType.value === 'custom_header') {
      if (customHeaderName.value !== (prev?.custom_header_name ?? '')) {
        data.custom_header_name = customHeaderName.value || null
      }
      if (customHeaderValue.value) data.custom_header_value = customHeaderValue.value
    }

    // When switching away from an auth type, clear its fields
    if (prev?.auth_type && authType.value !== prev.auth_type) {
      if (prev.auth_type === 'api_key' && authType.value !== 'oauth') {
        data.clear_api_key = true
      }
      if (prev.auth_type === 'oauth') {
        data.oauth_token_url = null
        data.oauth_client_id = null
        data.oauth_client_secret = null
        data.oauth_scope = null
      }
      if (prev.auth_type === 'custom_header') {
        data.custom_header_name = null
        data.custom_header_value = null
      }
    }

    emit('save', data)
  }
  // Dialog close is handled by the parent on success
}
</script>

<template>
  <Dialog
    :visible="visible"
    :header="mode === 'create' ? 'Add Provider' : `Edit ${providerName}`"
    modal
    class="w-[500px]"
    @update:visible="emit('update:visible', $event)"
  >
    <div class="space-y-4">
      <!-- Preset selector (create only) -->
      <div v-if="mode === 'create' && store.presets.length > 0">
        <label for="pf-preset" class="mb-1 block text-xs text-slate-400">From Preset</label>
        <Select
          v-model="selectedPreset"
          input-id="pf-preset"
          :options="store.presets"
          option-label="display_name"
          placeholder="Select a preset..."
          class="w-full"
        />
      </div>

      <!-- Name (create only) -->
      <div v-if="mode === 'create'">
        <label for="pf-name" class="mb-1 block text-xs text-slate-400">Name</label>
        <InputText id="pf-name" v-model="name" class="w-full" placeholder="my-provider" />
      </div>

      <!-- Driver -->
      <div>
        <label for="pf-driver" class="mb-1 block text-xs text-slate-400">Driver</label>
        <InputText id="pf-driver" v-model="driver" class="w-full" placeholder="litellm" />
      </div>

      <!-- Auth Type -->
      <div>
        <label for="pf-auth-type" class="mb-1 block text-xs text-slate-400">Auth Type</label>
        <Select
          v-model="authType"
          input-id="pf-auth-type"
          :options="AUTH_TYPE_OPTIONS"
          option-label="label"
          option-value="value"
          class="w-full"
        />
      </div>

      <!-- Base URL -->
      <div>
        <label for="pf-base-url" class="mb-1 block text-xs text-slate-400">Base URL</label>
        <InputText id="pf-base-url" v-model="baseUrl" class="w-full" placeholder="http://localhost:11434" />
      </div>

      <!-- API Key (api_key or oauth) -->
      <div v-if="authType === 'api_key' || authType === 'oauth'">
        <label for="pf-api-key" class="mb-1 block text-xs text-slate-400">
          {{ authType === 'oauth' ? 'Access Token (pre-fetched)' : 'API Key' }}
        </label>
        <InputText id="pf-api-key" v-model="apiKey" type="password" class="w-full" placeholder="sk-..." />
      </div>

      <!-- OAuth fields -->
      <template v-if="authType === 'oauth'">
        <div>
          <label for="pf-oauth-url" class="mb-1 block text-xs text-slate-400">Token URL</label>
          <InputText id="pf-oauth-url" v-model="oauthTokenUrl" class="w-full" placeholder="https://auth.example.com/token" />
        </div>
        <div>
          <label for="pf-oauth-id" class="mb-1 block text-xs text-slate-400">Client ID</label>
          <InputText id="pf-oauth-id" v-model="oauthClientId" class="w-full" />
        </div>
        <div>
          <label for="pf-oauth-secret" class="mb-1 block text-xs text-slate-400">Client Secret</label>
          <InputText id="pf-oauth-secret" v-model="oauthClientSecret" type="password" class="w-full" />
        </div>
        <div>
          <label for="pf-oauth-scope" class="mb-1 block text-xs text-slate-400">Scope (optional)</label>
          <InputText id="pf-oauth-scope" v-model="oauthScope" class="w-full" placeholder="read write" />
        </div>
      </template>

      <!-- Custom Header fields -->
      <template v-if="authType === 'custom_header'">
        <div>
          <label for="pf-header-name" class="mb-1 block text-xs text-slate-400">Header Name</label>
          <InputText id="pf-header-name" v-model="customHeaderName" class="w-full" placeholder="X-Api-Token" />
        </div>
        <div>
          <label for="pf-header-value" class="mb-1 block text-xs text-slate-400">Header Value</label>
          <InputText id="pf-header-value" v-model="customHeaderValue" type="password" class="w-full" />
        </div>
      </template>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <Button label="Cancel" severity="secondary" text @click="emit('update:visible', false)" />
        <Button :label="mode === 'create' ? 'Create' : 'Save'" :disabled="!isValid" @click="handleSave" />
      </div>
    </template>
  </Dialog>
</template>
