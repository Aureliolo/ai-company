<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import ToggleSwitch from 'primevue/toggleswitch'
import { useToast } from 'primevue/usetoast'
import AppShell from '@/components/layout/AppShell.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import ErrorBoundary from '@/components/common/ErrorBoundary.vue'
import ProviderCard from '@/components/providers/ProviderCard.vue'
import ProviderFormDialog from '@/components/providers/ProviderFormDialog.vue'
import SettingGroupRenderer from '@/components/settings/SettingGroupRenderer.vue'
import { useAuthStore } from '@/stores/auth'
import { useCompanyStore } from '@/stores/company'
import { useProviderStore } from '@/stores/providers'
import { useSettingsStore } from '@/stores/settings'
import { getErrorMessage } from '@/utils/errors'
import { MIN_PASSWORD_LENGTH, NAMESPACE_DISPLAY_NAMES } from '@/utils/constants'
import { sanitizeForLog } from '@/utils/logging'
import type { SettingEntry, SettingNamespace, CreateFromPresetRequest, CreateProviderRequest, UpdateProviderRequest } from '@/api/types'

const route = useRoute()
const toast = useToast()
const auth = useAuthStore()
const companyStore = useCompanyStore()
const providerStore = useProviderStore()
const settingsStore = useSettingsStore()
const loading = ref(true)

// Tab management -- dynamic namespace tabs + providers + user
const allTabValues = computed(() => {
  const nsTabs = settingsStore.namespaces.filter((ns) => ns !== 'providers')
  return [...nsTabs, 'providers', 'user'] as string[]
})

function resolveTab(raw: unknown): string {
  if (auth.mustChangePassword) return 'user'
  const s = String(raw ?? allTabValues.value[0] ?? 'user')
  return allTabValues.value.includes(s) ? s : (allTabValues.value[0] ?? 'user')
}

const activeTab = ref('user') // Will be resolved after data loads

watch(() => route.query.tab, (tab) => {
  activeTab.value = resolveTab(tab)
})

// Provider entries for the custom providers tab
const providerEntries = computed(() =>
  Object.entries(providerStore.providers).map(([name, config]) => ({ name, config })),
)

// Provider settings (non-configs entries) for the providers tab
const providerSettings = computed(() =>
  settingsStore.entriesByNamespace('providers').filter(
    (e) => e.definition.key !== 'configs',
  ),
)

// Password change state
const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const pwdError = ref<string | null>(null)

// Provider form dialog state
const formDialogVisible = ref(false)
const formDialogMode = ref<'create' | 'edit'>('create')
const editingProviderName = ref<string | undefined>(undefined)
const editingProviderConfig = computed(() =>
  editingProviderName.value ? providerStore.providers[editingProviderName.value] : undefined,
)

async function retryFetch() {
  loading.value = true
  try {
    await Promise.all([
      companyStore.fetchConfig(),
      providerStore.fetchProviders(),
      providerStore.fetchPresets(),
      settingsStore.fetchAll(),
    ])
    activeTab.value = resolveTab(route.query.tab)
  } catch (err) {
    // Surface fetch failure in the error boundary so the user sees it
    settingsStore.error = getErrorMessage(err)
    console.error('Settings data fetch failed:', sanitizeForLog(err))
  } finally {
    loading.value = false
  }
}

onMounted(retryFetch)

// Settings save/reset handlers
async function handleSettingSave(entry: SettingEntry, value: string) {
  try {
    await settingsStore.updateSetting(entry.definition.namespace, entry.definition.key, value)
    toast.add({ severity: 'success', summary: `${entry.definition.key} updated`, life: 3000 })
  } catch (err) {
    toast.add({ severity: 'error', summary: getErrorMessage(err), life: 5000 })
  }
}

async function handleSettingReset(entry: SettingEntry) {
  try {
    await settingsStore.resetSetting(entry.definition.namespace, entry.definition.key)
    toast.add({ severity: 'success', summary: `${entry.definition.key} reset to default`, life: 3000 })
  } catch (err) {
    toast.add({ severity: 'error', summary: getErrorMessage(err), life: 5000 })
  }
}

// Password change handler
async function handleChangePassword() {
  pwdError.value = null
  if (newPassword.value !== confirmPassword.value) {
    pwdError.value = 'Passwords do not match'
    return
  }
  if (newPassword.value.length < MIN_PASSWORD_LENGTH) {
    pwdError.value = `Password must be at least ${MIN_PASSWORD_LENGTH} characters`
    return
  }
  try {
    await auth.changePassword(currentPassword.value, newPassword.value)
    toast.add({ severity: 'success', summary: 'Password changed', life: 3000 })
    currentPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
  } catch (err) {
    pwdError.value = getErrorMessage(err)
  }
}

// Provider handlers
function openCreateDialog() {
  formDialogMode.value = 'create'
  editingProviderName.value = undefined
  formDialogVisible.value = true
}

function openEditDialog(name: string) {
  formDialogMode.value = 'edit'
  editingProviderName.value = name
  formDialogVisible.value = true
}

async function handleFormSave(data: CreateProviderRequest | UpdateProviderRequest) {
  try {
    if (formDialogMode.value === 'create') {
      await providerStore.createProvider(data as CreateProviderRequest)
      toast.add({ severity: 'success', summary: 'Provider created', life: 3000 })
    } else if (editingProviderName.value) {
      await providerStore.updateProvider(editingProviderName.value, data as UpdateProviderRequest)
      toast.add({ severity: 'success', summary: 'Provider updated', life: 3000 })
    }
    formDialogVisible.value = false
  } catch (err) {
    toast.add({ severity: 'error', summary: getErrorMessage(err), life: 5000 })
  }
}

async function handleFormSavePreset(data: CreateFromPresetRequest) {
  try {
    await providerStore.createFromPreset(data)
    toast.add({ severity: 'success', summary: 'Provider created from preset', life: 3000 })
    formDialogVisible.value = false
  } catch (err) {
    toast.add({ severity: 'error', summary: getErrorMessage(err), life: 5000 })
  }
}

async function handleDelete(name: string) {
  try {
    await providerStore.deleteProvider(name)
    toast.add({ severity: 'success', summary: `Provider ${name} deleted`, life: 3000 })
  } catch (err) {
    toast.add({ severity: 'error', summary: getErrorMessage(err), life: 5000 })
  }
}

function namespaceLabel(ns: SettingNamespace): string {
  return NAMESPACE_DISPLAY_NAMES[ns] ?? ns
}
</script>

<template>
  <AppShell>
    <PageHeader title="Settings" subtitle="Manage your dashboard configuration">
      <template #actions>
        <div class="flex items-center gap-2 text-sm text-slate-400">
          <span>Basic</span>
          <ToggleSwitch
            :model-value="settingsStore.showAdvanced"
            aria-label="Toggle advanced settings"
            @update:model-value="settingsStore.toggleAdvanced()"
          />
          <span>Advanced</span>
        </div>
      </template>
    </PageHeader>

    <ErrorBoundary :error="companyStore.configError ?? providerStore.error ?? settingsStore.error" @retry="retryFetch">
    <LoadingSkeleton v-if="loading" :lines="6" />
    <Tabs v-else :value="activeTab" @update:value="activeTab = String($event)">
      <TabList>
        <Tab
          v-for="ns in settingsStore.namespaces.filter((n) => n !== 'providers')"
          :key="ns"
          :value="ns"
          :disabled="auth.mustChangePassword"
        >
          {{ namespaceLabel(ns as SettingNamespace) }}
        </Tab>
        <Tab value="providers" :disabled="auth.mustChangePassword">Providers</Tab>
        <Tab value="user">User</Tab>
      </TabList>

      <TabPanels>
        <!-- Dynamic namespace tabs (except providers) -->
        <TabPanel
          v-for="ns in settingsStore.namespaces.filter((n) => n !== 'providers')"
          :key="ns"
          :value="ns"
        >
          <SettingGroupRenderer
            :entries="settingsStore.entriesByNamespace(ns as SettingNamespace)"
            :show-advanced="settingsStore.showAdvanced"
            :saving-key="settingsStore.savingKey"
            @save="handleSettingSave"
            @reset="handleSettingReset"
          />
        </TabPanel>

        <!-- Providers tab (custom UI + dynamic settings) -->
        <TabPanel value="providers">
          <div class="space-y-6">
            <!-- Provider cards (custom CRUD UI) -->
            <div class="space-y-4">
              <div class="flex items-center gap-2">
                <Button label="Add Provider" size="small" @click="openCreateDialog" />
              </div>

              <div v-if="providerEntries.length === 0" class="rounded-lg border border-dashed border-slate-700 p-8 text-center">
                <p class="text-sm text-slate-400">No providers configured. Add one to get started.</p>
              </div>

              <div v-else class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                <ProviderCard
                  v-for="entry in providerEntries"
                  :key="entry.name"
                  :name="entry.name"
                  :config="entry.config"
                  @edit="openEditDialog"
                  @delete="handleDelete"
                />
              </div>
            </div>

            <!-- Dynamic provider settings (routing strategy, retry, etc.) -->
            <SettingGroupRenderer
              v-if="providerSettings.length > 0"
              :entries="providerSettings"
              :show-advanced="settingsStore.showAdvanced"
              :saving-key="settingsStore.savingKey"
              @save="handleSettingSave"
              @reset="handleSettingReset"
            />
          </div>

          <ProviderFormDialog
            v-model:visible="formDialogVisible"
            :mode="formDialogMode"
            :provider-name="editingProviderName"
            :provider-config="editingProviderConfig"
            @save="handleFormSave"
            @save-preset="handleFormSavePreset"
          />
        </TabPanel>

        <!-- User Settings -->
        <TabPanel value="user">
          <div class="max-w-md space-y-4">
            <div class="rounded-lg border border-slate-800 p-4">
              <h4 class="mb-3 text-sm font-medium text-slate-300">Account Info</h4>
              <div class="space-y-2 text-sm">
                <div class="flex justify-between">
                  <span class="text-slate-400">Username</span>
                  <span class="text-slate-200">{{ auth.user?.username }}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-slate-400">Role</span>
                  <span class="text-slate-200">{{ auth.user?.role }}</span>
                </div>
              </div>
            </div>

            <div class="rounded-lg border border-slate-800 p-4">
              <h4 class="mb-3 text-sm font-medium text-slate-300">Change Password</h4>
              <form class="space-y-3" @submit.prevent="handleChangePassword">
                <div>
                  <label for="current-password" class="mb-1 block text-xs text-slate-400">Current Password</label>
                  <InputText id="current-password" v-model="currentPassword" type="password" class="w-full" placeholder="Current password" aria-required="true" :aria-describedby="pwdError ? 'pwd-error' : undefined" />
                </div>
                <div>
                  <label for="new-password" class="mb-1 block text-xs text-slate-400">New Password</label>
                  <InputText id="new-password" v-model="newPassword" type="password" class="w-full" :placeholder="`New password (min ${MIN_PASSWORD_LENGTH} chars)`" aria-required="true" :aria-describedby="pwdError ? 'pwd-error' : undefined" />
                </div>
                <div>
                  <label for="confirm-password" class="mb-1 block text-xs text-slate-400">Confirm Password</label>
                  <InputText id="confirm-password" v-model="confirmPassword" type="password" class="w-full" placeholder="Confirm new password" aria-required="true" :aria-describedby="pwdError ? 'pwd-error' : undefined" />
                </div>
                <div v-if="pwdError" id="pwd-error" role="alert" class="rounded bg-red-500/10 p-2 text-sm text-red-400">{{ pwdError }}</div>
                <Button
                  type="submit"
                  label="Change Password"
                  size="small"
                  :loading="auth.loading"
                  :disabled="!currentPassword || !newPassword || !confirmPassword"
                />
              </form>
            </div>
          </div>
        </TabPanel>
      </TabPanels>
    </Tabs>
    </ErrorBoundary>
  </AppShell>
</template>
