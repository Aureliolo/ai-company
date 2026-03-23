<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import Accordion from 'primevue/accordion'
import AccordionPanel from 'primevue/accordionpanel'
import AccordionHeader from 'primevue/accordionheader'
import AccordionContent from 'primevue/accordioncontent'
import Button from 'primevue/button'
import CodeEditor from '@/components/common/CodeEditor.vue'
import type { AutonomyLevel, DepartmentEntry } from '@/api/types'

const props = defineProps<{
  visible: boolean
  mode: 'create' | 'edit'
  department?: DepartmentEntry
  agentNames?: string[]
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  save: [department: DepartmentEntry]
}>()

const AUTONOMY_LEVELS: AutonomyLevel[] = ['full', 'semi', 'supervised', 'locked']

// Form state
const name = ref('')
const head = ref<string | null>(null)
const budgetPercent = ref<number | null>(null)
const autonomyLevel = ref<AutonomyLevel | null>(null)
const teamsJson = ref('[]')
const reportingLinesJson = ref('[]')
const policiesJson = ref('{}')

// Reset form when dialog opens, mode changes, or department changes
watch(
  [() => props.visible, () => props.mode, () => props.department],
  ([vis]) => {
    if (!vis) return
    jsonError.value = null
    if (props.mode === 'edit' && props.department) {
      name.value = props.department.name
      head.value = props.department.head ?? null
      budgetPercent.value = props.department.budget_percent ?? null
      autonomyLevel.value = props.department.autonomy_level ?? null
      teamsJson.value = JSON.stringify(
        props.department.teams ?? [], null, 2,
      )
      reportingLinesJson.value = JSON.stringify(
        props.department.reporting_lines ?? [], null, 2,
      )
      policiesJson.value = JSON.stringify(
        props.department.policies ?? {}, null, 2,
      )
    } else {
      name.value = ''
      head.value = null
      budgetPercent.value = null
      autonomyLevel.value = null
      teamsJson.value = '[]'
      reportingLinesJson.value = '[]'
      policiesJson.value = '{}'
    }
  },
)

const jsonError = ref<string | null>(null)

function tryParseJsonArray(text: string, label: string): unknown[] | null {
  try {
    const parsed = JSON.parse(text)
    if (!Array.isArray(parsed)) {
      jsonError.value = `${label} must be a JSON array`
      return null
    }
    return parsed
  } catch {
    jsonError.value = `${label} contains invalid JSON`
    return null
  }
}

function tryParseJsonObject(text: string, label: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(text)
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      jsonError.value = `${label} must be a JSON object`
      return null
    }
    return parsed as Record<string, unknown>
  } catch {
    jsonError.value = `${label} contains invalid JSON`
    return null
  }
}

const canSave = computed(() => name.value.trim().length > 0)

function handleSave() {
  jsonError.value = null
  const teams = tryParseJsonArray(teamsJson.value, 'Teams')
  if (teams === null) return
  const reportingLines = tryParseJsonArray(reportingLinesJson.value, 'Reporting Lines')
  if (reportingLines === null) return
  const policies = tryParseJsonObject(policiesJson.value, 'Policies')
  if (policies === null) return

  const dept: DepartmentEntry = {
    name: name.value.trim(),
    budget_percent: budgetPercent.value ?? undefined,
    autonomy_level: autonomyLevel.value ?? undefined,
    teams: teams as DepartmentEntry['teams'],
    reporting_lines: reportingLines as DepartmentEntry['reporting_lines'],
    policies: policies as Record<string, unknown>,
  }
  // PrimeVue Select show-clear sets value to null, so coerce before trim
  const trimmedHead = (head.value ?? '').trim()
  if (trimmedHead) dept.head = trimmedHead

  emit('save', dept)
  // Dialog close is controlled by the parent after async save succeeds
}
</script>

<template>
  <Dialog
    :visible="visible"
    :header="mode === 'create' ? 'Add Department' : 'Edit Department'"
    modal
    class="w-full max-w-2xl"
    @update:visible="emit('update:visible', $event)"
  >
    <div class="space-y-4">
      <!-- Top-level fields -->
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label
            for="dept-name"
            class="mb-1 block text-xs text-slate-400"
          >
            Name <span class="text-red-400">*</span>
          </label>
          <InputText
            id="dept-name"
            v-model="name"
            class="w-full"
            :disabled="mode === 'edit'"
            placeholder="e.g. engineering"
          />
        </div>
        <div>
          <label
            for="dept-head"
            class="mb-1 block text-xs text-slate-400"
          >
            Head (agent name)
          </label>
          <Select
            v-model="head"
            input-id="dept-head"
            :options="agentNames ?? []"
            class="w-full"
            show-clear
            placeholder="Select an agent"
          />
        </div>
        <div>
          <label
            for="dept-budget"
            class="mb-1 block text-xs text-slate-400"
          >Budget %</label>
          <InputNumber
            v-model="budgetPercent"
            input-id="dept-budget"
            :min="0"
            :max="100"
            :use-grouping="false"
            class="w-full"
            placeholder="0-100"
          />
        </div>
        <div>
          <label
            for="dept-autonomy"
            class="mb-1 block text-xs text-slate-400"
          >Autonomy Level (optional)</label>
          <Select
            v-model="autonomyLevel"
            input-id="dept-autonomy"
            :options="AUTONOMY_LEVELS"
            class="w-full"
            placeholder="Inherit from company"
            show-clear
          />
        </div>
      </div>

      <!-- Nested structures as accordion -->
      <Accordion multiple>
        <AccordionPanel value="teams">
          <AccordionHeader>Teams</AccordionHeader>
          <AccordionContent>
            <p class="mb-2 text-xs text-slate-400">
              Array of team objects with name, lead, and members fields.
            </p>
            <CodeEditor
              v-model="teamsJson"
              language="json"
              min-height="100px"
            />
          </AccordionContent>
        </AccordionPanel>
        <AccordionPanel value="reporting">
          <AccordionHeader>Reporting Lines</AccordionHeader>
          <AccordionContent>
            <p class="mb-2 text-xs text-slate-400">
              Array of objects with subordinate and supervisor agent names.
            </p>
            <CodeEditor
              v-model="reportingLinesJson"
              language="json"
              min-height="100px"
            />
          </AccordionContent>
        </AccordionPanel>
        <AccordionPanel value="policies">
          <AccordionHeader>Policies</AccordionHeader>
          <AccordionContent>
            <p class="mb-2 text-xs text-slate-400">
              Object with review_requirements and approval_chains.
            </p>
            <CodeEditor
              v-model="policiesJson"
              language="json"
              min-height="100px"
            />
          </AccordionContent>
        </AccordionPanel>
      </Accordion>

      <!-- JSON validation error -->
      <div
        v-if="jsonError"
        role="alert"
        class="rounded bg-red-500/10 p-2 text-xs text-red-400"
      >
        {{ jsonError }}
      </div>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <Button
          label="Cancel"
          severity="secondary"
          text
          size="small"
          @click="emit('update:visible', false)"
        />
        <Button
          :label="mode === 'create' ? 'Add Department' : 'Save'"
          size="small"
          :disabled="!canSave"
          @click="handleSave"
        />
      </div>
    </template>
  </Dialog>
</template>
