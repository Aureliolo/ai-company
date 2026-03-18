<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import { useToast } from 'primevue/usetoast'
import AppShell from '@/components/layout/AppShell.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import ErrorBoundary from '@/components/common/ErrorBoundary.vue'
import ProviderCard from '@/components/providers/ProviderCard.vue'
import ProviderFormDialog from '@/components/providers/ProviderFormDialog.vue'
import { useAuthStore } from '@/stores/auth'
import { useCompanyStore } from '@/stores/company'
import { useProviderStore } from '@/stores/providers'
import { getErrorMessage } from '@/utils/errors'
import { MIN_PASSWORD_LENGTH } from '@/utils/constants'
import { sanitizeForLog } from '@/utils/logging'
import type { CreateFromPresetRequest, CreateProviderRequest, UpdateProviderRequest } from '@/api/types'

const route = useRoute()
const toast = useToast()
const auth = useAuthStore()
const companyStore = useCompanyStore()
const providerStore = useProviderStore()
const loading = ref(true)

const VALID_TABS = ['company', 'providers', 'user'] as const
function resolveTab(raw: unknown): string {
  if (auth.mustChangePassword) return 'user'
  const s = String(raw ?? 'company')
  return VALID_TABS.includes(s as typeof VALID_TABS[number]) ? s : 'company'
}
const activeTab = ref(resolveTab(route.query.tab))

watch(() => route.query.tab, (tab) => {
  activeTab.value = resolveTab(tab)
})

const providerEntries = computed(() =>
  Object.entries(providerStore.providers).map(([name, config]) => ({ name, config })),
)

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
    ])
  } catch (err) {
    console.error('Settings data fetch failed:', sanitizeForLog(err))
  } finally {
    loading.value = false
  }
}

onMounted(retryFetch)

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
</script>

<template>
  <AppShell>
    <PageHeader title="Settings" subtitle="Manage your dashboard configuration" />

    <ErrorBoundary :error="companyStore.configError ?? providerStore.error" @retry="retryFetch">
    <LoadingSkeleton v-if="loading" :lines="6" />
    <TabView v-else :value="activeTab" @update:value="auth.mustChangePassword ? undefined : (activeTab = $event)">
      <!-- Company Config -->
      <TabPanel header="Company" value="company" :disabled="auth.mustChangePassword">
        <div v-if="companyStore.config" class="space-y-4">
          <div class="rounded-lg border border-slate-800 p-4">
            <h4 class="mb-3 text-sm font-medium text-slate-300">Company Name</h4>
            <p class="text-lg text-slate-200">{{ companyStore.config.company_name }}</p>
          </div>
          <div class="rounded-lg border border-slate-800 p-4">
            <h4 class="mb-3 text-sm font-medium text-slate-300">Agents ({{ companyStore.config.agents.length }})</h4>
            <div class="flex flex-wrap gap-2">
              <span
                v-for="agent in companyStore.config.agents"
                :key="agent.name"
                class="rounded bg-slate-800 px-2 py-1 text-xs text-slate-300"
              >
                {{ agent.name }} ({{ agent.role }})
              </span>
            </div>
          </div>
        </div>
      </TabPanel>

      <!-- Providers -->
      <TabPanel header="Providers" value="providers" :disabled="auth.mustChangePassword">
        <div class="space-y-4">
          <div class="flex items-center gap-2">
            <Button label="Add Provider" size="small" @click="openCreateDialog" />
          </div>

          <!-- Empty state -->
          <div v-if="providerEntries.length === 0" class="rounded-lg border border-dashed border-slate-700 p-8 text-center">
            <p class="text-sm text-slate-400">No providers configured. Add one to get started.</p>
          </div>

          <!-- Provider cards grid -->
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
      <TabPanel header="User" value="user">
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
    </TabView>
    </ErrorBoundary>
  </AppShell>
</template>
