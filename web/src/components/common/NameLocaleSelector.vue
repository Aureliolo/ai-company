<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import ToggleSwitch from 'primevue/toggleswitch'
import Checkbox from 'primevue/checkbox'
import * as setupApi from '@/api/endpoints/setup'
import { getErrorMessage } from '@/utils/errors'

const props = defineProps<{
  /** Currently selected locale codes, or ['__all__']. */
  modelValue: string[]
}>()

const emit = defineEmits<{
  'update:modelValue': [locales: string[]]
}>()

const ALL_SENTINEL = '__all__'

const loading = ref(true)
const error = ref<string | null>(null)
const regions = ref<Record<string, string[]>>({})
const displayNames = ref<Record<string, string>>({})

/** Flat set of all known locale codes. */
const allLocales = computed(() => {
  const codes: string[] = []
  for (const locales of Object.values(regions.value)) {
    codes.push(...locales)
  }
  return new Set(codes)
})

const isAll = computed(() =>
  props.modelValue.length === 1 && props.modelValue[0] === ALL_SENTINEL,
)

const selectedSet = computed(() => new Set(props.modelValue))

function toggleAll(value: boolean) {
  if (value) {
    emit('update:modelValue', [ALL_SENTINEL])
  } else {
    // Deselect all -- start with empty selection
    emit('update:modelValue', [])
  }
}

function isRegionSelected(regionLocales: string[]): boolean {
  if (isAll.value) return true
  return regionLocales.every((loc) => selectedSet.value.has(loc))
}

function isRegionPartial(regionLocales: string[]): boolean {
  if (isAll.value) return false
  const count = regionLocales.filter((loc) => selectedSet.value.has(loc)).length
  return count > 0 && count < regionLocales.length
}

function toggleRegion(regionLocales: string[], selected: boolean) {
  const current = new Set(props.modelValue.filter((l) => l !== ALL_SENTINEL))
  if (selected) {
    for (const loc of regionLocales) current.add(loc)
  } else {
    for (const loc of regionLocales) current.delete(loc)
  }
  // If all locales are now selected, switch to ALL sentinel
  if (current.size === allLocales.value.size) {
    emit('update:modelValue', [ALL_SENTINEL])
  } else {
    emit('update:modelValue', [...current])
  }
}

function isLocaleSelected(locale: string): boolean {
  if (isAll.value) return true
  return selectedSet.value.has(locale)
}

function toggleLocale(locale: string, selected: boolean) {
  const current = new Set(props.modelValue.filter((l) => l !== ALL_SENTINEL))
  if (isAll.value) {
    // Switching from "all" to individual -- start with all and remove this one
    for (const loc of allLocales.value) current.add(loc)
  }
  if (selected) {
    current.add(locale)
  } else {
    current.delete(locale)
  }
  // If all locales are now selected, switch to ALL sentinel
  if (current.size === allLocales.value.size) {
    emit('update:modelValue', [ALL_SENTINEL])
  } else {
    emit('update:modelValue', [...current])
  }
}

// Watch for external "all" toggle-off to expand to individual locales
watch(isAll, (newVal, oldVal) => {
  if (oldVal && !newVal && props.modelValue.length === 0) {
    // User toggled off "all" -- leave empty for manual selection
  }
})

onMounted(async () => {
  try {
    const data = await setupApi.getAvailableLocales()
    regions.value = data.regions
    displayNames.value = data.display_names
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <!-- Loading -->
    <div v-if="loading" class="text-center">
      <i class="pi pi-spin pi-spinner text-slate-400" />
      <p class="mt-1 text-xs text-slate-500">Loading locales...</p>
    </div>

    <!-- Error -->
    <div
      v-else-if="error"
      role="alert"
      class="rounded bg-red-500/10 p-3 text-center text-sm text-red-400"
    >
      {{ error }}
    </div>

    <!-- Locale selector -->
    <div v-else>
      <!-- All toggle -->
      <div class="mb-4 flex items-center gap-3 rounded-lg border border-slate-700 bg-slate-900 p-3">
        <ToggleSwitch
          :model-value="isAll"
          aria-label="Select all locales worldwide"
          @update:model-value="toggleAll"
        />
        <div>
          <span class="text-sm font-medium text-slate-100">All (worldwide)</span>
          <p class="text-xs text-slate-500">
            Generate names from all {{ allLocales.size }} Latin-script locales
          </p>
        </div>
      </div>

      <!-- Region groups -->
      <div class="space-y-3">
        <div
          v-for="(locales, region) in regions"
          :key="region"
          class="rounded-lg border border-slate-700 bg-slate-900 p-3"
        >
          <!-- Region header with checkbox -->
          <div class="mb-2 flex items-center gap-2">
            <Checkbox
              :model-value="isRegionSelected(locales)"
              :binary="true"
              :indeterminate="isRegionPartial(locales)"
              :aria-label="`Select all ${region} locales`"
              @update:model-value="toggleRegion(locales, $event)"
            />
            <span class="text-sm font-medium text-slate-200">{{ region }}</span>
            <span class="text-xs text-slate-500">({{ locales.length }})</span>
          </div>

          <!-- Individual locale chips -->
          <div class="flex flex-wrap gap-1.5 pl-7">
            <label
              v-for="locale in locales"
              :key="locale"
              class="inline-flex cursor-pointer items-center gap-1 rounded-full px-2.5 py-1 text-xs transition-colors"
              :class="
                isLocaleSelected(locale)
                  ? 'bg-brand-600/20 text-brand-300 border border-brand-600/40'
                  : 'bg-slate-800 text-slate-400 border border-slate-700 hover:border-slate-600'
              "
            >
              <input
                type="checkbox"
                class="sr-only"
                :checked="isLocaleSelected(locale)"
                :aria-label="displayNames[locale] || locale"
                @change="toggleLocale(locale, ($event.target as HTMLInputElement).checked)"
              />
              {{ displayNames[locale] || locale }}
            </label>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
