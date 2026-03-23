<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Button from 'primevue/button'
import ConfirmDialog from 'primevue/confirmdialog'
import { useConfirm } from 'primevue/useconfirm'
import { useToast } from 'primevue/usetoast'
import AppShell from '@/components/layout/AppShell.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import ErrorBoundary from '@/components/common/ErrorBoundary.vue'
import EditModeToggle from '@/components/common/EditModeToggle.vue'
import ProviderCard from '@/components/providers/ProviderCard.vue'
import ProviderFormDialog from '@/components/providers/ProviderFormDialog.vue'
import SettingGroupRenderer from '@/components/settings/SettingGroupRenderer.vue'
import SettingsCodeView from '@/components/settings/SettingsCodeView.vue'
import { useProviderStore } from '@/stores/providers'
import { useSettingsStore } from '@/stores/settings'
import { useEditMode } from '@/composables/useEditMode'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'
import type {
  SettingEntry,
  SettingNamespace,
  CreateFromPresetRequest,
  CreateProviderRequest,
  UpdateProviderRequest,
} from '@/api/types'

const confirm = useConfirm()
const toast = useToast()
const providerStore = useProviderStore()
const settingsStore = useSettingsStore()
const editMode = useEditMode()
const loading = ref(true)

// Provider entries for the card grid
const providerEntries = computed(() =>
  Object.entries(providerStore.providers).map(([name, config]) => ({ name, config })),
)

// Provider-namespace settings excluding the 'configs' key (shown via ProviderCard grid above)
const providerSettings = computed(() =>
  settingsStore.entriesByNamespace('providers').filter(
    (e) => e.definition.key !== 'configs',
  ),
)

/** Effective edit mode for provider settings section. */
const providersEditMode = editMode.getEffectiveMode('providers')
const providersCodeMode = computed(() => {
  const mode = providersEditMode.value
  return mode === 'yaml' ? 'yaml' : 'json'
})

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
      providerStore.fetchProviders(),
      providerStore.fetchPresets(),
      settingsStore.fetchAll(),
    ])
  } catch (err) {
    console.error('Providers data fetch failed:', sanitizeForLog(err))
  } finally {
    loading.value = false
  }
}

onMounted(retryFetch)

// Provider CRUD handlers
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

async function handleFormSave(
  data: CreateProviderRequest | UpdateProviderRequest,
) {
  try {
    if (formDialogMode.value === 'create') {
      await providerStore.createProvider(
        data as CreateProviderRequest,
      )
      toast.add({
        severity: 'success',
        summary: 'Provider created',
        life: 3000,
      })
    } else if (editingProviderName.value) {
      await providerStore.updateProvider(
        editingProviderName.value,
        data as UpdateProviderRequest,
      )
      toast.add({
        severity: 'success',
        summary: 'Provider updated',
        life: 3000,
      })
    }
    formDialogVisible.value = false
  } catch (err) {
    toast.add({
      severity: 'error',
      summary: getErrorMessage(err),
      life: 5000,
    })
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

function handleDelete(name: string) {
  const shortName = name.slice(0, 64)
  confirm.require({
    header: 'Delete Provider',
    message: `Delete provider "${shortName}"? Credentials will be lost.`,
    acceptClass: 'p-button-danger',
    accept: async () => {
      try {
        await providerStore.deleteProvider(name)
        toast.add({
          severity: 'success',
          summary: `Provider ${shortName} deleted`,
          life: 3000,
        })
      } catch (err) {
        toast.add({
          severity: 'error',
          summary: getErrorMessage(err),
          life: 5000,
        })
      }
    },
  })
}

// Settings handlers
async function handleSettingSave(
  entry: SettingEntry, value: string,
) {
  const { namespace, key } = entry.definition
  try {
    await settingsStore.updateSetting(namespace, key, value)
    toast.add({
      severity: 'success',
      summary: `${key} updated`,
      life: 3000,
    })
  } catch (err) {
    toast.add({
      severity: 'error',
      summary: getErrorMessage(err),
      life: 5000,
    })
  }
}

async function handleSettingReset(entry: SettingEntry) {
  const { namespace, key } = entry.definition
  try {
    await settingsStore.resetSetting(namespace, key)
    toast.add({
      severity: 'success',
      summary: `${key} reset to default`,
      life: 3000,
    })
  } catch (err) {
    toast.add({
      severity: 'error',
      summary: getErrorMessage(err),
      life: 5000,
    })
  }
}

function handleDirty(payload: {
  namespace: SettingNamespace
  key: string
  value: string
  isDirty: boolean
}) {
  if (payload.isDirty) {
    settingsStore.setDirty(
      payload.namespace, payload.key, payload.value,
    )
  } else {
    settingsStore.clearDirty(payload.namespace, payload.key)
  }
}

async function handleCodeViewSave(
  updates: Array<{
    namespace: SettingNamespace
    key: string
    value: string
  }>,
) {
  const results = await Promise.allSettled(
    updates.map((u) =>
      settingsStore.updateSetting(u.namespace, u.key, u.value),
    ),
  )
  const saved = results.filter(
    (r) => r.status === 'fulfilled',
  ).length
  const failed = results.filter(
    (r) => r.status === 'rejected',
  ).length
  if (saved > 0) {
    toast.add({
      severity: 'success',
      summary: `${saved} setting(s) saved`,
      life: 3000,
    })
  }
  if (failed > 0) {
    toast.add({
      severity: 'error',
      summary: `${failed} setting(s) failed to save`,
      life: 5000,
    })
  }
}
</script>

<template>
  <AppShell>
    <PageHeader
      title="Providers"
      subtitle="Manage LLM provider connections and routing"
    />

    <ErrorBoundary
      :error="providerStore.error ?? settingsStore.error"
      @retry="retryFetch"
    >
      <LoadingSkeleton
        v-if="loading"
        :lines="6"
      />
      <div
        v-else
        class="space-y-8"
      >
        <!-- Provider CRUD section -->
        <section>
          <div class="mb-4 flex items-center gap-2">
            <Button
              label="Add Provider"
              size="small"
              @click="openCreateDialog"
            />
          </div>

          <div
            v-if="providerEntries.length === 0"
            class="rounded-lg border border-dashed border-slate-700 p-8 text-center"
          >
            <p class="text-sm text-slate-400">
              No providers configured. Add one to get started.
            </p>
          </div>

          <div
            v-else
            class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3"
          >
            <ProviderCard
              v-for="entry in providerEntries"
              :key="entry.name"
              :name="entry.name"
              :config="entry.config"
              @edit="openEditDialog"
              @delete="handleDelete"
            />
          </div>
        </section>

        <!-- Provider settings section -->
        <section v-if="providerSettings.length > 0">
          <div class="mb-4 flex items-center justify-between">
            <h3 class="text-sm font-medium text-slate-300">
              Provider Settings
            </h3>
            <EditModeToggle
              :model-value="providersEditMode"
              size="small"
              @update:model-value="editMode.setTabMode('providers', $event)"
            />
          </div>

          <SettingGroupRenderer
            v-if="providersEditMode === 'gui'"
            :entries="providerSettings"
            :show-advanced="settingsStore.showAdvanced"
            :saving-key="settingsStore.savingKey"
            @save="handleSettingSave"
            @reset="handleSettingReset"
            @dirty="handleDirty"
          />
          <SettingsCodeView
            v-else
            :entries="providerSettings"
            :mode="providersCodeMode"
            :saving="settingsStore.savingKey !== null"
            @save="handleCodeViewSave"
          />
        </section>
      </div>
    </ErrorBoundary>

    <ConfirmDialog />
    <ProviderFormDialog
      v-model:visible="formDialogVisible"
      :mode="formDialogMode"
      :provider-name="editingProviderName"
      :provider-config="editingProviderConfig"
      @save="handleFormSave"
      @save-preset="handleFormSavePreset"
    />
  </AppShell>
</template>
