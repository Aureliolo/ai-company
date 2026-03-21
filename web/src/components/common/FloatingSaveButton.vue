<script setup lang="ts">
import Button from 'primevue/button'
import Badge from 'primevue/badge'

defineProps<{
  count: number
  loading: boolean
}>()

defineEmits<{
  click: []
}>()
</script>

<template>
  <Transition
    enter-active-class="transition duration-200 ease-out"
    enter-from-class="translate-y-4 opacity-0"
    enter-to-class="translate-y-0 opacity-100"
    leave-active-class="transition duration-150 ease-in"
    leave-from-class="translate-y-0 opacity-100"
    leave-to-class="translate-y-4 opacity-0"
  >
    <div v-if="count > 0" class="fixed bottom-6 right-6 z-50">
      <Button
        :label="`Save All Modified (${count})`"
        icon="pi pi-save"
        severity="success"
        :loading="loading"
        raised
        @click="$emit('click')"
      >
        <template #icon>
          <i class="pi pi-save mr-2" aria-hidden="true" />
        </template>
      </Button>
    </div>
  </Transition>
</template>
