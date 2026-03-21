<script setup lang="ts">
import { computed } from 'vue'
import { Codemirror } from 'vue-codemirror'
import { json } from '@codemirror/lang-json'
import { yaml } from '@codemirror/lang-yaml'
import { oneDark } from '@codemirror/theme-one-dark'

const props = withDefaults(
  defineProps<{
    modelValue: string
    language?: 'json' | 'yaml'
    readonly?: boolean
    minHeight?: string
  }>(),
  { language: 'json', readonly: false, minHeight: '120px' },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const extensions = computed(() => {
  const exts = [oneDark]
  if (props.language === 'yaml') {
    exts.push(yaml())
  } else {
    exts.push(json())
  }
  return exts
})

function handleUpdate(value: string) {
  emit('update:modelValue', value)
}
</script>

<template>
  <div
    class="code-editor-wrapper overflow-hidden rounded-lg border border-slate-700"
    :style="{ minHeight }"
  >
    <Codemirror
      :model-value="modelValue"
      :extensions="extensions"
      :disabled="readonly"
      :style="{ minHeight }"
      @update:model-value="handleUpdate"
    />
  </div>
</template>

<style scoped>
.code-editor-wrapper :deep(.cm-editor) {
  font-size: 0.8125rem;
  border-radius: 0.5rem;
}

.code-editor-wrapper :deep(.cm-editor.cm-focused) {
  outline: none;
}

.code-editor-wrapper :deep(.cm-scroller) {
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas,
    'Liberation Mono', monospace;
}
</style>
