<script setup lang="ts">
import type { EditMode } from '@/composables/useEditMode'
import SelectButton from 'primevue/selectbutton'

withDefaults(
  defineProps<{
    modelValue: EditMode
    size?: 'small' | 'normal'
  }>(),
  { size: 'normal' },
)

const emit = defineEmits<{
  'update:modelValue': [value: EditMode]
}>()

const options = [
  { label: 'GUI', value: 'gui' as const },
  { label: 'JSON', value: 'json' as const },
  { label: 'YAML', value: 'yaml' as const },
]
</script>

<template>
  <SelectButton
    :model-value="modelValue"
    :options="options"
    :allow-empty="false"
    option-label="label"
    option-value="value"
    :class="{ 'p-selectbutton-sm': size === 'small' }"
    aria-label="Edit mode"
    @update:model-value="emit('update:modelValue', $event)"
  />
</template>

<style scoped>
.p-selectbutton-sm :deep(.p-togglebutton) {
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
}
</style>
