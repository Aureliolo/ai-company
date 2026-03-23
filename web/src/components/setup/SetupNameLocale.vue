<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Button from 'primevue/button'
import NameLocaleSelector from '@/components/common/NameLocaleSelector.vue'
import { useSetupStore } from '@/stores/setup'
import { getErrorMessage } from '@/utils/errors'
import { sanitizeForLog } from '@/utils/logging'

const emit = defineEmits<{
  next: []
  previous: []
}>()

const setup = useSetupStore()

const error = ref<string | null>(null)
const saving = ref(false)
const loading = ref(true)
const loadFailed = ref(false)
const selectedLocales = ref<string[]>([])

async function handleNext() {
  if (saving.value || loading.value || loadFailed.value) return
  saving.value = true
  error.value = null
  try {
    await setup.saveNameLocales(selectedLocales.value)
    emit('next')
  } catch (err) {
    error.value = getErrorMessage(err)
  } finally {
    saving.value = false
  }
}

async function fetchLocales() {
  loading.value = true
  loadFailed.value = false
  error.value = null
  try {
    const locales = await setup.fetchNameLocales()
    selectedLocales.value = locales.length > 0 ? locales : ['__all__']
  } catch (err) {
    console.warn('[SetupNameLocale] Failed to load saved locales:', sanitizeForLog(err))
    error.value = 'Could not load your saved locale preferences. Please retry.'
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

onMounted(fetchLocales)
</script>

<template>
  <div class="mx-auto w-full max-w-3xl">
    <div class="mb-6 text-center">
      <h2 class="text-2xl font-semibold text-slate-100">
        Name Generation
      </h2>
      <p class="mt-1 text-sm text-slate-400">
        Choose where agent names are generated from.
        Select "All" for worldwide diversity, or pick specific regions.
      </p>
    </div>

    <!-- Error -->
    <div
      v-if="error"
      role="alert"
      class="mb-4 rounded bg-red-500/10 p-3 text-center text-sm text-red-400"
    >
      {{ error }}
      <button
        v-if="loadFailed"
        type="button"
        class="ml-2 underline hover:text-red-300"
        @click="fetchLocales"
      >
        Retry
      </button>
    </div>

    <!-- Locale selector -->
    <div class="mb-6">
      <NameLocaleSelector v-model="selectedLocales" />
    </div>

    <!-- Navigation -->
    <div class="flex items-center justify-between">
      <Button
        label="Back"
        severity="secondary"
        icon="pi pi-arrow-left"
        @click="$emit('previous')"
      />
      <Button
        label="Next"
        icon="pi pi-arrow-right"
        icon-pos="right"
        :loading="saving || loading"
        :disabled="selectedLocales.length === 0 || loading || loadFailed"
        @click="handleNext"
      />
    </div>
  </div>
</template>
