<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Button from 'primevue/button'
import { useProviderStore } from '@/stores/providers'
import type {
  AuthType,
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
    oauthTokenUrl.value = ''
    oauthClientId.value = ''
    oauthClientSecret.value = ''
    oauthScope.value = ''
    customHeaderName.value = ''
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
  name.value = preset.name
})

const isValid = computed(() => {
  if (props.mode === 'create' && !name.value.trim()) return false
  if (!driver.value.trim()) return false
  return true
})

function handleSave() {
  if (props.mode === 'create') {
    const data: CreateProviderRequest = {
      name: name.value,
      driver: driver.value,
      auth_type: authType.value,
    }
    if (baseUrl.value) data.base_url = baseUrl.value
    if (apiKey.value) data.api_key = apiKey.value
    if (oauthTokenUrl.value) data.oauth_token_url = oauthTokenUrl.value
    if (oauthClientId.value) data.oauth_client_id = oauthClientId.value
    if (oauthClientSecret.value) data.oauth_client_secret = oauthClientSecret.value
    if (oauthScope.value) data.oauth_scope = oauthScope.value
    if (customHeaderName.value) data.custom_header_name = customHeaderName.value
    if (customHeaderValue.value) data.custom_header_value = customHeaderValue.value
    emit('save', data)
  } else {
    const data: UpdateProviderRequest = {}
    if (driver.value !== props.providerConfig?.driver) data.driver = driver.value
    if (authType.value !== props.providerConfig?.auth_type) data.auth_type = authType.value
    if (baseUrl.value) data.base_url = baseUrl.value
    if (apiKey.value) data.api_key = apiKey.value
    if (oauthTokenUrl.value) data.oauth_token_url = oauthTokenUrl.value
    if (oauthClientId.value) data.oauth_client_id = oauthClientId.value
    if (oauthClientSecret.value) data.oauth_client_secret = oauthClientSecret.value
    if (oauthScope.value) data.oauth_scope = oauthScope.value
    if (customHeaderName.value) data.custom_header_name = customHeaderName.value
    if (customHeaderValue.value) data.custom_header_value = customHeaderValue.value
    emit('save', data)
  }
  emit('update:visible', false)
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
        <label class="mb-1 block text-xs text-slate-400">From Preset</label>
        <Select
          v-model="selectedPreset"
          :options="store.presets"
          option-label="display_name"
          placeholder="Select a preset..."
          class="w-full"
        />
      </div>

      <!-- Name (create only) -->
      <div v-if="mode === 'create'">
        <label class="mb-1 block text-xs text-slate-400">Name</label>
        <InputText v-model="name" class="w-full" placeholder="my-provider" />
      </div>

      <!-- Driver -->
      <div>
        <label class="mb-1 block text-xs text-slate-400">Driver</label>
        <InputText v-model="driver" class="w-full" placeholder="litellm" />
      </div>

      <!-- Auth Type -->
      <div>
        <label class="mb-1 block text-xs text-slate-400">Auth Type</label>
        <Select
          v-model="authType"
          :options="AUTH_TYPE_OPTIONS"
          option-label="label"
          option-value="value"
          class="w-full"
        />
      </div>

      <!-- Base URL -->
      <div>
        <label class="mb-1 block text-xs text-slate-400">Base URL</label>
        <InputText v-model="baseUrl" class="w-full" placeholder="http://localhost:11434" />
      </div>

      <!-- API Key (api_key or oauth) -->
      <div v-if="authType === 'api_key' || authType === 'oauth'">
        <label class="mb-1 block text-xs text-slate-400">API Key</label>
        <InputText v-model="apiKey" type="password" class="w-full" placeholder="sk-..." />
      </div>

      <!-- OAuth fields -->
      <template v-if="authType === 'oauth'">
        <div>
          <label class="mb-1 block text-xs text-slate-400">Token URL</label>
          <InputText v-model="oauthTokenUrl" class="w-full" placeholder="https://auth.example.com/token" />
        </div>
        <div>
          <label class="mb-1 block text-xs text-slate-400">Client ID</label>
          <InputText v-model="oauthClientId" class="w-full" />
        </div>
        <div>
          <label class="mb-1 block text-xs text-slate-400">Client Secret</label>
          <InputText v-model="oauthClientSecret" type="password" class="w-full" />
        </div>
        <div>
          <label class="mb-1 block text-xs text-slate-400">Scope (optional)</label>
          <InputText v-model="oauthScope" class="w-full" placeholder="read write" />
        </div>
      </template>

      <!-- Custom Header fields -->
      <template v-if="authType === 'custom_header'">
        <div>
          <label class="mb-1 block text-xs text-slate-400">Header Name</label>
          <InputText v-model="customHeaderName" class="w-full" placeholder="X-Api-Token" />
        </div>
        <div>
          <label class="mb-1 block text-xs text-slate-400">Header Value</label>
          <InputText v-model="customHeaderValue" type="password" class="w-full" />
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
