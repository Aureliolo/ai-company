<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Button from 'primevue/button'
import NameLocaleSelector from '@/components/common/NameLocaleSelector.vue'
import { useSettingsStore } from '@/stores/settings'
import { useToast } from 'primevue/usetoast'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'

const settingsStore = useSettingsStore()
const toast = useToast()

const selectedLocales = ref<string[]>(['__all__'])
const saving = ref(false)
const dirty = ref(false)

async function loadLocales() {
  // Read from settings store (company.name_locales)
  const entry = settingsStore.entriesByNamespace('company')
    .find((e) => e.definition.key === 'name_locales')
  if (entry?.value) {
    try {
      const parsed = JSON.parse(entry.value)
      if (Array.isArray(parsed)) {
        selectedLocales.value = parsed
      } else {
        console.warn('[SettingsNameLocales] name_locales setting is not an array:', sanitizeForLog(parsed))
        toast.add({
          severity: 'warn',
          summary: 'Saved locale preference is corrupted. Showing default.',
          life: 5000,
        })
      }
    } catch (err) {
      console.warn('[SettingsNameLocales] Failed to parse name_locales:', sanitizeForLog(err))
      toast.add({
        severity: 'warn',
        summary: 'Could not load saved locale preference. Showing default.',
        life: 5000,
      })
    }
  }
}

function handleUpdate(locales: string[]) {
  selectedLocales.value = locales
  dirty.value = true
}

async function handleSave() {
  if (saving.value) return
  saving.value = true
  try {
    await settingsStore.updateSetting('company', 'name_locales', JSON.stringify(selectedLocales.value))
    dirty.value = false
    toast.add({ severity: 'success', summary: 'Name locales updated', life: 3000 })
  } catch (err) {
    toast.add({ severity: 'error', summary: getErrorMessage(err), life: 5000 })
  } finally {
    saving.value = false
  }
}

onMounted(loadLocales)
</script>

<template>
  <div class="mt-6 rounded-lg border border-slate-800 p-4">
    <div class="mb-4 flex items-center justify-between">
      <div>
        <h4 class="text-sm font-medium text-slate-300">
          Name Locales
        </h4>
        <p class="mt-0.5 text-xs text-slate-500">
          Choose which regions agent names are generated from.
        </p>
      </div>
      <Button
        v-if="dirty"
        label="Save"
        size="small"
        :loading="saving"
        @click="handleSave"
      />
    </div>
    <NameLocaleSelector
      :model-value="selectedLocales"
      @update:model-value="handleUpdate"
    />
  </div>
</template>
