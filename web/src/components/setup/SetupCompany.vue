<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Button from 'primevue/button'
import { useSetupStore } from '@/stores/setup'
import * as setupApi from '@/api/endpoints/setup'
import { getErrorMessage } from '@/utils/errors'

const emit = defineEmits<{
  next: [companyName: string]
  previous: []
}>()

const setup = useSetupStore()

const companyName = ref('')
const companyDescription = ref('')
const selectedTemplate = ref<string | null>(null)
const error = ref<string | null>(null)
const creating = ref(false)
/** Whether the user clicked Edit on the completed summary. */
const editing = ref(false)
/** Stored result from a successful creation (for the summary view). */
const createdResult = ref<{
  companyName: string
  templateApplied: string | null
  departmentCount: number
} | null>(null)

const isValid = computed(() => companyName.value.trim().length > 0)

/** Whether to show the completed summary. */
const showSummary = computed(() =>
  setup.isStepComplete('company') && !editing.value && createdResult.value !== null,
)

function selectTemplate(templateName: string | null) {
  selectedTemplate.value = templateName
}

function startEditing() {
  if (createdResult.value) {
    companyName.value = createdResult.value.companyName
  }
  editing.value = true
}

async function handleCreate() {
  if (!isValid.value || creating.value) return
  creating.value = true
  error.value = null
  try {
    const result = await setupApi.createCompany({
      company_name: companyName.value.trim(),
      description: companyDescription.value.trim() || null,
      template_name: selectedTemplate.value,
    })
    createdResult.value = {
      companyName: result.company_name,
      templateApplied: result.template_applied,
      departmentCount: result.department_count,
    }
    editing.value = false
    emit('next', companyName.value.trim())
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    creating.value = false
  }
}

onMounted(async () => {
  await setup.fetchTemplates()
  // fetchTemplates catches errors internally; surface to component.
  if (setup.error) {
    error.value = setup.error
  }
})
</script>

<template>
  <div class="mx-auto w-full max-w-lg">
    <div class="mb-6 text-center">
      <h2 class="text-2xl font-semibold text-slate-100">Create Your Company</h2>
      <p class="mt-1 text-sm text-slate-400">
        Name your synthetic organization and optionally start from a template.
      </p>
    </div>

    <!-- Completed summary -->
    <template v-if="showSummary">
      <div class="rounded-lg border border-green-500/20 bg-green-500/10 p-4">
        <div class="mb-3 flex items-center gap-2">
          <i class="pi pi-check-circle text-xl text-green-400" />
          <span class="text-sm font-medium text-green-300">Company created</span>
        </div>
        <div class="space-y-1 text-sm text-slate-300">
          <p>Name: <strong>{{ createdResult?.companyName ?? 'Your Company' }}</strong></p>
          <p>Template: {{ createdResult?.templateApplied ?? 'Start Blank' }}</p>
          <p>Departments: {{ createdResult?.departmentCount ?? 0 }}</p>
        </div>
        <Button
          label="Edit"
          icon="pi pi-pencil"
          severity="secondary"
          size="small"
          outlined
          class="mt-3"
          @click="startEditing"
        />
      </div>
      <div class="mt-8 flex items-center gap-3">
        <Button
          type="button"
          label="Back"
          icon="pi pi-arrow-left"
          severity="secondary"
          outlined
          @click="emit('previous')"
        />
        <Button
          label="Next"
          icon="pi pi-arrow-right"
          icon-pos="right"
          class="flex-1"
          @click="emit('next', createdResult?.companyName ?? '')"
        />
      </div>
    </template>

    <!-- Creation/edit form -->
    <template v-else>
      <form class="space-y-6" @submit.prevent="handleCreate">
        <div>
          <label for="sc-name" class="mb-1 block text-sm text-slate-300">Company Name</label>
          <InputText
            id="sc-name"
            v-model="companyName"
            class="w-full"
            placeholder="My AI Company"
          />
        </div>

        <div>
          <label for="sc-description" class="mb-1 block text-sm text-slate-300">
            Description <span class="text-slate-500">(optional)</span>
          </label>
          <Textarea
            id="sc-description"
            v-model="companyDescription"
            class="w-full"
            rows="3"
            maxlength="1000"
            placeholder="Describe what your organization does..."
          />
        </div>

        <!-- Template selector -->
        <div>
          <p class="mb-3 text-sm text-slate-300">Choose a template (optional)</p>
          <div class="grid gap-3" :class="setup.templates.length > 2 ? 'grid-cols-2' : 'grid-cols-1'">
            <!-- Start blank option -->
            <button
              type="button"
              class="rounded-lg border p-4 text-left transition-colors"
              :class="
                selectedTemplate === null
                  ? 'border-brand-600 bg-brand-600/10'
                  : 'border-slate-700 bg-slate-900 hover:border-slate-500'
              "
              @click="selectTemplate(null)"
            >
              <div class="mb-1 text-sm font-medium text-slate-100">Start Blank</div>
              <p class="text-xs text-slate-400">Begin with an empty organization.</p>
            </button>

            <!-- Template cards -->
            <button
              v-for="tmpl in setup.templates"
              :key="tmpl.name"
              type="button"
              class="rounded-lg border p-4 text-left transition-colors"
              :class="
                selectedTemplate === tmpl.name
                  ? 'border-brand-600 bg-brand-600/10'
                  : 'border-slate-700 bg-slate-900 hover:border-slate-500'
              "
              @click="selectTemplate(tmpl.name)"
            >
              <div class="mb-1 text-sm font-medium text-slate-100">{{ tmpl.display_name }}</div>
              <p class="text-xs text-slate-400">{{ tmpl.description }}</p>
            </button>
          </div>
        </div>

        <div
          v-if="error"
          role="alert"
          class="rounded bg-red-500/10 p-3 text-sm text-red-400"
        >
          {{ error }}
        </div>

        <div class="flex items-center gap-3">
          <Button
            type="button"
            label="Back"
            icon="pi pi-arrow-left"
            severity="secondary"
            outlined
            :disabled="creating"
            @click="emit('previous')"
          />
          <Button
            type="submit"
            :label="editing ? 'Update Company' : 'Create Company'"
            icon="pi pi-building"
            class="flex-1"
            :loading="creating"
            :disabled="!isValid"
          />
        </div>
      </form>
    </template>
  </div>
</template>
