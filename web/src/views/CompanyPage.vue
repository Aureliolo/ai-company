<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import Button from 'primevue/button'
import ConfirmDialog from 'primevue/confirmdialog'
import { useConfirm } from 'primevue/useconfirm'
import { useToast } from 'primevue/usetoast'
import AppShell from '@/components/layout/AppShell.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import ErrorBoundary from '@/components/common/ErrorBoundary.vue'
import EditModeToggle from '@/components/common/EditModeToggle.vue'
import CompanyGeneralForm from '@/components/company/CompanyGeneralForm.vue'
import CompanyAgentCard from '@/components/company/CompanyAgentCard.vue'
import CompanyAgentFormDialog from '@/components/company/CompanyAgentFormDialog.vue'
import CompanyDepartmentCard from '@/components/company/CompanyDepartmentCard.vue'
import CompanyDepartmentFormDialog from '@/components/company/CompanyDepartmentFormDialog.vue'
import SettingsCodeView from '@/components/settings/SettingsCodeView.vue'
import { useSettingsStore } from '@/stores/settings'
import { useEditMode } from '@/composables/useEditMode'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'
import type { AgentConfigEntry, DepartmentEntry, SettingEntry, SettingNamespace } from '@/api/types'

const confirm = useConfirm()
const toast = useToast()
const settingsStore = useSettingsStore()
const editMode = useEditMode()
const loading = ref(true)
const activeTab = ref('general')

// Company entries from settings
const companyEntries = computed(() => settingsStore.entriesByNamespace('company'))

// Company name for page title
const companyName = computed(() => {
  const entry = companyEntries.value.find((e) => e.definition.key === 'company_name')
  return entry?.value || 'Company'
})

// Parse agents from JSON setting -- surface errors instead of silently returning []
function parseJsonArray(entries: SettingEntry[], key: string): { data: unknown[]; error: string | null } {
  const entry = entries.find((e) => e.definition.key === key)
  if (!entry?.value) return { data: [], error: null }
  try {
    const parsed = JSON.parse(entry.value)
    return { data: Array.isArray(parsed) ? parsed : [], error: null }
  } catch (err) {
    return {
      data: [],
      error: `Failed to parse ${key} JSON: ${err instanceof Error ? err.message : 'invalid JSON'}. Use code mode to fix.`,
    }
  }
}

const agentsParsed = computed(() => parseJsonArray(companyEntries.value, 'agents'))
const agents = computed<AgentConfigEntry[]>(() => agentsParsed.value.data as AgentConfigEntry[])
const agentParseError = computed(() => agentsParsed.value.error)

const deptsParsed = computed(() => parseJsonArray(companyEntries.value, 'departments'))
const departments = computed<DepartmentEntry[]>(() => deptsParsed.value.data as DepartmentEntry[])
const deptParseError = computed(() => deptsParsed.value.error)

// Department names for agent form dropdown
const departmentNames = computed(() => departments.value.map((d) => d.name))

/** Effective edit mode for the company page (cast-safe for template). */
const companyEditMode = editMode.getEffectiveMode('company')
const companyCodeMode = computed(() => {
  const mode = companyEditMode.value
  return mode === 'yaml' ? 'yaml' : 'json'
})

// Agent form dialog state
const agentDialogVisible = ref(false)
const agentDialogMode = ref<'create' | 'edit'>('create')
const editingAgentIndex = ref(-1)
const editingAgent = computed(() =>
  editingAgentIndex.value >= 0 ? agents.value[editingAgentIndex.value] : undefined,
)

// Department form dialog state
const deptDialogVisible = ref(false)
const deptDialogMode = ref<'create' | 'edit'>('create')
const editingDeptIndex = ref(-1)
const editingDept = computed(() =>
  editingDeptIndex.value >= 0 ? departments.value[editingDeptIndex.value] : undefined,
)

async function retryFetch() {
  loading.value = true
  try {
    await settingsStore.fetchAll()
  } catch (err) {
    console.error('Company data fetch failed:', sanitizeForLog(err))
  } finally {
    loading.value = false
  }
}

onMounted(retryFetch)

// ── Agent CRUD ─────────────────────────────────────────────

function openAddAgent() {
  agentDialogMode.value = 'create'
  editingAgentIndex.value = -1
  agentDialogVisible.value = true
}

function openEditAgent(index: number) {
  agentDialogMode.value = 'edit'
  editingAgentIndex.value = index
  agentDialogVisible.value = true
}

async function saveAgent(agent: AgentConfigEntry) {
  const updated = [...agents.value]
  if (agentDialogMode.value === 'edit' && editingAgentIndex.value >= 0) {
    updated[editingAgentIndex.value] = agent
  } else {
    updated.push(agent)
  }
  try {
    await settingsStore.updateSetting(
      'company', 'agents', JSON.stringify(updated),
    )
    agentDialogVisible.value = false
    const action = agentDialogMode.value === 'create' ? 'added' : 'updated'
    toast.add({
      severity: 'success',
      summary: `Agent ${agent.name.slice(0, 64)} ${action}`,
      life: 3000,
    })
  } catch (err) {
    toast.add({ severity: 'error', summary: getErrorMessage(err), life: 5000 })
  }
}

function deleteAgent(index: number) {
  const agent = agents.value[index]
  const shortName = agent.name.slice(0, 64)
  confirm.require({
    header: 'Delete Agent',
    message: `Are you sure you want to delete agent "${shortName}"?`,
    acceptClass: 'p-button-danger',
    accept: async () => {
      const updated = agents.value.filter((_, i) => i !== index)
      try {
        await settingsStore.updateSetting(
          'company', 'agents', JSON.stringify(updated),
        )
        toast.add({
          severity: 'success',
          summary: `Agent ${shortName} deleted`,
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

// ── Department CRUD ────────────────────────────────────────

function openAddDept() {
  deptDialogMode.value = 'create'
  editingDeptIndex.value = -1
  deptDialogVisible.value = true
}

function openEditDept(index: number) {
  deptDialogMode.value = 'edit'
  editingDeptIndex.value = index
  deptDialogVisible.value = true
}

async function saveDept(dept: DepartmentEntry) {
  const updated = [...departments.value]
  if (deptDialogMode.value === 'edit' && editingDeptIndex.value >= 0) {
    updated[editingDeptIndex.value] = dept
  } else {
    updated.push(dept)
  }
  try {
    await settingsStore.updateSetting(
      'company', 'departments', JSON.stringify(updated),
    )
    deptDialogVisible.value = false
    const action = deptDialogMode.value === 'create' ? 'added' : 'updated'
    toast.add({
      severity: 'success',
      summary: `Department ${dept.name.slice(0, 64)} ${action}`,
      life: 3000,
    })
  } catch (err) {
    toast.add({ severity: 'error', summary: getErrorMessage(err), life: 5000 })
  }
}

function deleteDept(index: number) {
  const dept = departments.value[index]
  const shortName = dept.name.slice(0, 64)
  confirm.require({
    header: 'Delete Department',
    message: `Are you sure you want to delete department "${shortName}"?`,
    acceptClass: 'p-button-danger',
    accept: async () => {
      const updated = departments.value.filter((_, i) => i !== index)
      try {
        await settingsStore.updateSetting(
          'company', 'departments', JSON.stringify(updated),
        )
        toast.add({
          severity: 'success',
          summary: `Department ${shortName} deleted`,
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

// ── Settings handlers (for general form) ───────────────────

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

async function handleCodeViewSave(updates: Array<{ namespace: SettingNamespace; key: string; value: string }>) {
  const results = await Promise.allSettled(
    updates.map((u) => settingsStore.updateSetting(u.namespace, u.key, u.value)),
  )
  const saved = results.filter((r) => r.status === 'fulfilled').length
  const failed = results.filter((r) => r.status === 'rejected').length
  if (saved > 0) toast.add({ severity: 'success', summary: `${saved} setting(s) saved`, life: 3000 })
  if (failed > 0) toast.add({ severity: 'error', summary: `${failed} setting(s) failed to save`, life: 5000 })
}
</script>

<template>
  <AppShell>
    <PageHeader :title="companyName" subtitle="Company configuration, agents, and departments">
      <template #actions>
        <EditModeToggle
          :model-value="companyEditMode"
          size="small"
          @update:model-value="editMode.setTabMode('company', $event)"
        />
      </template>
    </PageHeader>

    <ErrorBoundary :error="settingsStore.error" @retry="retryFetch">
    <LoadingSkeleton v-if="loading" :lines="6" />

    <!-- Code view mode (JSON/YAML) -->
    <SettingsCodeView
      v-else-if="companyEditMode !== 'gui'"
      :entries="companyEntries"
      :mode="companyCodeMode"
      :saving="settingsStore.savingKey !== null"
      @save="handleCodeViewSave"
    />

    <!-- GUI mode -->
    <Tabs v-else v-model:value="activeTab">
      <TabList>
        <Tab value="general">General</Tab>
        <Tab value="agents">Agents ({{ agents.length }})</Tab>
        <Tab value="departments">Departments ({{ departments.length }})</Tab>
      </TabList>

      <TabPanels>
        <!-- General tab -->
        <TabPanel value="general">
          <CompanyGeneralForm
            :entries="companyEntries"
            :saving-key="settingsStore.savingKey"
            @save="handleSettingSave"
            @reset="handleSettingReset"
          />
        </TabPanel>

        <!-- Agents tab -->
        <TabPanel value="agents">
          <div v-if="agentParseError" role="alert" class="mb-4 rounded bg-red-500/10 p-3 text-sm text-red-400">
            {{ agentParseError }}
          </div>
          <div class="mb-4">
            <Button label="Add Agent" size="small" :disabled="!!agentParseError" @click="openAddAgent" />
          </div>

          <div
            v-if="!agentParseError && agents.length === 0"
            class="rounded-lg border border-dashed border-slate-700 p-8 text-center"
          >
            <p class="text-sm text-slate-400">No agents configured. Add one to get started.</p>
          </div>

          <div v-else class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            <CompanyAgentCard
              v-for="(agent, index) in agents"
              :key="agent.name"
              :agent="agent"
              :index="index"
              @edit="openEditAgent"
              @delete="deleteAgent"
            />
          </div>
        </TabPanel>

        <!-- Departments tab -->
        <TabPanel value="departments">
          <div v-if="deptParseError" role="alert" class="mb-4 rounded bg-red-500/10 p-3 text-sm text-red-400">
            {{ deptParseError }}
          </div>
          <div class="mb-4">
            <Button label="Add Department" size="small" :disabled="!!deptParseError" @click="openAddDept" />
          </div>

          <div
            v-if="!deptParseError && departments.length === 0"
            class="rounded-lg border border-dashed border-slate-700 p-8 text-center"
          >
            <p class="text-sm text-slate-400">No departments configured. Add one to get started.</p>
          </div>

          <div v-else class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            <CompanyDepartmentCard
              v-for="(dept, index) in departments"
              :key="dept.name"
              :department="dept"
              :index="index"
              @edit="openEditDept"
              @delete="deleteDept"
            />
          </div>
        </TabPanel>
      </TabPanels>
    </Tabs>
    </ErrorBoundary>

    <!-- Dialogs -->
    <CompanyAgentFormDialog
      v-model:visible="agentDialogVisible"
      :mode="agentDialogMode"
      :agent="editingAgent"
      :departments="departmentNames"
      @save="saveAgent"
    />
    <CompanyDepartmentFormDialog
      v-model:visible="deptDialogVisible"
      :mode="deptDialogMode"
      :department="editingDept"
      @save="saveDept"
    />
    <ConfirmDialog />
  </AppShell>
</template>
