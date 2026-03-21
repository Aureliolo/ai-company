<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Accordion from 'primevue/accordion'
import AccordionPanel from 'primevue/accordionpanel'
import AccordionHeader from 'primevue/accordionheader'
import AccordionContent from 'primevue/accordioncontent'
import Button from 'primevue/button'
import CodeEditor from '@/components/common/CodeEditor.vue'
import type { AgentConfigEntry, SeniorityLevel, AutonomyLevel } from '@/api/types'

const props = defineProps<{
  visible: boolean
  mode: 'create' | 'edit'
  agent?: AgentConfigEntry
  departments?: string[]
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  save: [agent: AgentConfigEntry]
}>()

const LEVELS: SeniorityLevel[] = ['junior', 'mid', 'senior', 'lead', 'principal', 'director', 'vp', 'c_suite']
const AUTONOMY_LEVELS: AutonomyLevel[] = ['full', 'semi', 'supervised', 'locked']

// Form state
const name = ref('')
const role = ref('')
const department = ref('')
const level = ref<SeniorityLevel>('mid')
const autonomyLevel = ref<AutonomyLevel | null>(null)
const personalityJson = ref('{}')
const modelJson = ref('{}')
const memoryJson = ref('{}')
const toolsJson = ref('{}')
const authorityJson = ref('{}')

// Reset form when dialog opens or agent changes
watch(() => props.visible, (vis) => {
  if (!vis) return
  if (props.mode === 'edit' && props.agent) {
    name.value = props.agent.name
    role.value = props.agent.role
    department.value = props.agent.department
    level.value = props.agent.level
    autonomyLevel.value = props.agent.autonomy_level ?? null
    personalityJson.value = JSON.stringify(props.agent.personality ?? {}, null, 2)
    modelJson.value = JSON.stringify(props.agent.model ?? {}, null, 2)
    memoryJson.value = JSON.stringify(props.agent.memory ?? {}, null, 2)
    toolsJson.value = JSON.stringify(props.agent.tools ?? {}, null, 2)
    authorityJson.value = JSON.stringify(props.agent.authority ?? {}, null, 2)
  } else {
    name.value = ''
    role.value = ''
    department.value = ''
    level.value = 'mid'
    autonomyLevel.value = null
    personalityJson.value = '{}'
    modelJson.value = '{}'
    memoryJson.value = '{}'
    toolsJson.value = '{}'
    authorityJson.value = '{}'
  }
})

const jsonError = ref<string | null>(null)

function tryParseJson(text: string, label: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(text)
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      jsonError.value = `${label} must be a JSON object`
      return null
    }
    return parsed
  } catch {
    jsonError.value = `${label} contains invalid JSON`
    return null
  }
}

const canSave = computed(() => name.value.trim() && role.value.trim() && department.value.trim())

function handleSave() {
  jsonError.value = null
  const personality = tryParseJson(personalityJson.value, 'Personality')
  if (personality === null) return
  const model = tryParseJson(modelJson.value, 'Model')
  if (model === null) return
  const memory = tryParseJson(memoryJson.value, 'Memory')
  if (memory === null) return
  const tools = tryParseJson(toolsJson.value, 'Tools')
  if (tools === null) return
  const authority = tryParseJson(authorityJson.value, 'Authority')
  if (authority === null) return

  emit('save', {
    name: name.value.trim(),
    role: role.value.trim(),
    department: department.value.trim(),
    level: level.value,
    autonomy_level: autonomyLevel.value,
    personality,
    model,
    memory,
    tools,
    authority,
  })
  emit('update:visible', false)
}
</script>

<template>
  <Dialog
    :visible="visible"
    :header="mode === 'create' ? 'Add Agent' : 'Edit Agent'"
    modal
    class="w-full max-w-2xl"
    @update:visible="emit('update:visible', $event)"
  >
    <div class="space-y-4">
      <!-- Top-level fields -->
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label for="agent-name" class="mb-1 block text-xs text-slate-400">Name</label>
          <InputText id="agent-name" v-model="name" class="w-full" :disabled="mode === 'edit'" placeholder="agent-name" />
        </div>
        <div>
          <label for="agent-role" class="mb-1 block text-xs text-slate-400">Role</label>
          <InputText id="agent-role" v-model="role" class="w-full" placeholder="e.g. CTO" />
        </div>
        <div>
          <label for="agent-department" class="mb-1 block text-xs text-slate-400">Department</label>
          <Select
            v-if="departments && departments.length > 0"
            input-id="agent-department"
            v-model="department"
            :options="departments"
            class="w-full"
            editable
            placeholder="Select or type..."
          />
          <InputText v-else id="agent-department" v-model="department" class="w-full" placeholder="e.g. engineering" />
        </div>
        <div>
          <label for="agent-level" class="mb-1 block text-xs text-slate-400">Level</label>
          <Select input-id="agent-level" v-model="level" :options="LEVELS" class="w-full" />
        </div>
        <div>
          <label for="agent-autonomy" class="mb-1 block text-xs text-slate-400">Autonomy Level (optional)</label>
          <Select
            input-id="agent-autonomy"
            v-model="autonomyLevel"
            :options="AUTONOMY_LEVELS"
            class="w-full"
            placeholder="Inherit from company"
            show-clear
          />
        </div>
      </div>

      <!-- Nested sub-objects as accordion -->
      <Accordion multiple>
        <AccordionPanel value="personality">
          <AccordionHeader>Personality</AccordionHeader>
          <AccordionContent>
            <CodeEditor v-model="personalityJson" language="json" min-height="100px" />
          </AccordionContent>
        </AccordionPanel>
        <AccordionPanel value="model">
          <AccordionHeader>Model</AccordionHeader>
          <AccordionContent>
            <CodeEditor v-model="modelJson" language="json" min-height="100px" />
          </AccordionContent>
        </AccordionPanel>
        <AccordionPanel value="memory">
          <AccordionHeader>Memory</AccordionHeader>
          <AccordionContent>
            <CodeEditor v-model="memoryJson" language="json" min-height="100px" />
          </AccordionContent>
        </AccordionPanel>
        <AccordionPanel value="tools">
          <AccordionHeader>Tools</AccordionHeader>
          <AccordionContent>
            <CodeEditor v-model="toolsJson" language="json" min-height="100px" />
          </AccordionContent>
        </AccordionPanel>
        <AccordionPanel value="authority">
          <AccordionHeader>Authority</AccordionHeader>
          <AccordionContent>
            <CodeEditor v-model="authorityJson" language="json" min-height="100px" />
          </AccordionContent>
        </AccordionPanel>
      </Accordion>

      <!-- JSON validation error -->
      <div v-if="jsonError" role="alert" class="rounded bg-red-500/10 p-2 text-xs text-red-400">
        {{ jsonError }}
      </div>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <Button label="Cancel" severity="secondary" text size="small" @click="emit('update:visible', false)" />
        <Button :label="mode === 'create' ? 'Add Agent' : 'Save'" size="small" :disabled="!canSave" @click="handleSave" />
      </div>
    </template>
  </Dialog>
</template>
