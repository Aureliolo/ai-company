<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import Password from 'primevue/password'
import Button from 'primevue/button'
import ToggleSwitch from 'primevue/toggleswitch'
import { useToast } from 'primevue/usetoast'
import AppShell from '@/components/layout/AppShell.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import ErrorBoundary from '@/components/common/ErrorBoundary.vue'
import EditModeToggle from '@/components/common/EditModeToggle.vue'
import AdvancedWarningDialog from '@/components/common/AdvancedWarningDialog.vue'
import AdvancedBanner from '@/components/common/AdvancedBanner.vue'
import FloatingSaveButton from '@/components/common/FloatingSaveButton.vue'
import SettingGroupRenderer from '@/components/settings/SettingGroupRenderer.vue'
import SettingsCodeView from '@/components/settings/SettingsCodeView.vue'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'
import { useEditMode } from '@/composables/useEditMode'
import { getErrorMessage } from '@/utils/errors'
import { MIN_PASSWORD_LENGTH, NAMESPACE_DISPLAY_NAMES } from '@/utils/constants'
import { sanitizeForLog } from '@/utils/logging'
import type { SettingEntry, SettingNamespace } from '@/api/types'

const route = useRoute()
const toast = useToast()
const auth = useAuthStore()
const settingsStore = useSettingsStore()
const editMode = useEditMode()
const loading = ref(true)

// Advanced warning dialog
const showWarningDialog = ref(false)

// Tab management -- dynamic namespace tabs + user
const allTabValues = computed(() => {
  return [...settingsStore.namespaces, 'user'] as string[]
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

// Password change state
const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const pwdError = ref<string | null>(null)

async function retryFetch() {
  loading.value = true
  try {
    await settingsStore.fetchAll()
    activeTab.value = resolveTab(route.query.tab)
  } catch (err) {
    settingsStore.error = getErrorMessage(err)
    console.error('Settings data fetch failed:', sanitizeForLog(err))
  } finally {
    loading.value = false
  }
}

onMounted(retryFetch)

// Advanced toggle with warning
function handleAdvancedToggle() {
  const result = settingsStore.toggleAdvanced()
  if (result === 'needs_warning') {
    showWarningDialog.value = true
  }
}

function handleAdvancedConfirm() {
  settingsStore.confirmAdvanced()
}

// Settings save/reset handlers
async function handleSettingSave(entry: SettingEntry, value: string) {
  try {
    await settingsStore.updateSetting(entry.definition.namespace, entry.definition.key, value)
    settingsStore.clearDirty(entry.definition.namespace, entry.definition.key)
    toast.add({ severity: 'success', summary: `${entry.definition.key} updated`, life: 3000 })
  } catch (err) {
    toast.add({ severity: 'error', summary: getErrorMessage(err), life: 5000 })
  }
}

async function handleSettingReset(entry: SettingEntry) {
  try {
    await settingsStore.resetSetting(entry.definition.namespace, entry.definition.key)
    settingsStore.clearDirty(entry.definition.namespace, entry.definition.key)
    toast.add({ severity: 'success', summary: `${entry.definition.key} reset to default`, life: 3000 })
  } catch (err) {
    toast.add({ severity: 'error', summary: getErrorMessage(err), life: 5000 })
  }
}

// Code view save handler
async function handleCodeViewSave(updates: Array<{ namespace: string; key: string; value: string }>) {
  let saved = 0
  let failed = 0
  for (const u of updates) {
    try {
      await settingsStore.updateSetting(u.namespace as SettingNamespace, u.key, u.value)
      saved++
    } catch {
      failed++
    }
  }
  if (saved > 0) {
    toast.add({ severity: 'success', summary: `${saved} setting(s) saved`, life: 3000 })
  }
  if (failed > 0) {
    toast.add({ severity: 'error', summary: `${failed} setting(s) failed to save`, life: 5000 })
  }
}

// Dirty tracking
function handleDirty(payload: { namespace: SettingNamespace; key: string; value: string; isDirty: boolean }) {
  if (payload.isDirty) {
    settingsStore.setDirty(payload.namespace, payload.key, payload.value)
  } else {
    settingsStore.clearDirty(payload.namespace, payload.key)
  }
}

async function handleSaveAllDirty() {
  const { saved, failed } = await settingsStore.saveAllDirty()
  if (saved > 0) {
    toast.add({ severity: 'success', summary: `${saved} setting(s) saved`, life: 3000 })
  }
  if (failed > 0) {
    toast.add({ severity: 'error', summary: `${failed} setting(s) failed to save`, life: 5000 })
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

function namespaceLabel(ns: SettingNamespace): string {
  return NAMESPACE_DISPLAY_NAMES[ns] ?? ns
}

/** Get the code mode for a namespace (excluding 'gui'). */
function getCodeMode(ns: string): 'json' | 'yaml' {
  const mode = editMode.getEffectiveMode(ns).value
  return mode === 'yaml' ? 'yaml' : 'json'
}
</script>

<template>
  <AppShell>
    <PageHeader title="Settings" subtitle="Manage your dashboard configuration">
      <template #actions>
        <div class="flex items-center gap-4">
          <EditModeToggle
            :model-value="editMode.globalMode.value"
            size="small"
            @update:model-value="editMode.setGlobalMode"
          />
          <div class="flex items-center gap-2 text-sm text-slate-400">
            <span>Basic</span>
            <ToggleSwitch
              :model-value="settingsStore.showAdvanced"
              aria-label="Toggle advanced settings"
              @update:model-value="handleAdvancedToggle()"
            />
            <span>Advanced</span>
          </div>
        </div>
      </template>
    </PageHeader>

    <AdvancedBanner :visible="settingsStore.showAdvanced" class="mb-4" />

    <ErrorBoundary :error="settingsStore.error" @retry="retryFetch">
    <LoadingSkeleton v-if="loading" :lines="6" />
    <Tabs v-else :value="activeTab" @update:value="activeTab = String($event)">
      <TabList>
        <Tab
          v-for="ns in settingsStore.namespaces"
          :key="ns"
          :value="ns"
          :disabled="auth.mustChangePassword"
        >
          {{ namespaceLabel(ns as SettingNamespace) }}
        </Tab>
        <Tab value="user">User</Tab>
      </TabList>

      <TabPanels>
        <!-- Dynamic namespace tabs -->
        <TabPanel
          v-for="ns in settingsStore.namespaces"
          :key="ns"
          :value="ns"
        >
          <!-- Per-tab edit mode override -->
          <div class="mb-4 flex items-center justify-between">
            <h3 class="text-sm font-medium text-slate-300">{{ namespaceLabel(ns as SettingNamespace) }} Settings</h3>
            <EditModeToggle
              :model-value="editMode.getEffectiveMode(ns).value"
              size="small"
              @update:model-value="editMode.setTabMode(ns, $event)"
            />
          </div>

          <!-- GUI mode -->
          <SettingGroupRenderer
            v-if="editMode.getEffectiveMode(ns).value === 'gui'"
            :entries="settingsStore.entriesByNamespace(ns as SettingNamespace)"
            :show-advanced="settingsStore.showAdvanced"
            :saving-key="settingsStore.savingKey"
            @save="handleSettingSave"
            @reset="handleSettingReset"
            @dirty="handleDirty"
          />

          <!-- JSON / YAML mode -->
          <SettingsCodeView
            v-else
            :entries="settingsStore.entriesByNamespace(ns as SettingNamespace)"
            :mode="getCodeMode(ns)"
            :saving="settingsStore.savingKey !== null"
            @save="handleCodeViewSave"
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
                  <Password inputId="current-password" v-model="currentPassword" :toggle-mask="true" :feedback="false" fluid placeholder="Current password" :input-props="{ autocomplete: 'current-password', 'aria-required': 'true', 'aria-describedby': pwdError ? 'pwd-error' : undefined }" />
                </div>
                <div>
                  <label for="new-password" class="mb-1 block text-xs text-slate-400">New Password</label>
                  <Password inputId="new-password" v-model="newPassword" :toggle-mask="true" :feedback="false" fluid :placeholder="`New password (min ${MIN_PASSWORD_LENGTH} chars)`" :input-props="{ autocomplete: 'new-password', 'aria-required': 'true', 'aria-describedby': pwdError ? 'pwd-error' : undefined }" />
                </div>
                <div>
                  <label for="confirm-password" class="mb-1 block text-xs text-slate-400">Confirm Password</label>
                  <Password inputId="confirm-password" v-model="confirmPassword" :toggle-mask="true" :feedback="false" fluid placeholder="Confirm new password" :input-props="{ autocomplete: 'new-password', 'aria-required': 'true', 'aria-describedby': pwdError ? 'pwd-error' : undefined }" />
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

    <!-- Floating save all button -->
    <FloatingSaveButton
      :count="settingsStore.dirtyCount"
      :loading="settingsStore.savingAll"
      @click="handleSaveAllDirty"
    />

    <!-- Advanced warning dialog -->
    <AdvancedWarningDialog
      v-model:visible="showWarningDialog"
      @confirm="handleAdvancedConfirm"
    />
  </AppShell>
</template>
