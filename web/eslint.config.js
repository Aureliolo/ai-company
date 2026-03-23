import pluginVue from 'eslint-plugin-vue'
import pluginSecurity from 'eslint-plugin-security'
import tsParser from '@typescript-eslint/parser'

export default [
  {
    ignores: ['dist/**'],
  },
  ...pluginVue.configs['flat/recommended'],
  pluginSecurity.configs.recommended,
  {
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: {
        parser: tsParser,
      },
    },
  },
  {
    files: ['**/*.ts'],
    languageOptions: {
      parser: tsParser,
    },
  },
  {
    rules: {
      'no-unassigned-vars': 'error',
      'no-useless-assignment': 'error',
      'preserve-caught-error': 'error',
      'vue/no-v-html': 'warn',
      // Rule flags every obj[var] with no data-flow analysis (20/23 warnings
      // were false positives). Prototype pollution is guarded explicitly in
      // providers.ts (Object.create(null) + __proto__/constructor/prototype
      // filtering). Future dynamic property access with untrusted keys should
      // be manually reviewed.
      'security/detect-object-injection': 'off',
    },
  },
  {
    files: ['src/App.vue', 'src/components/layout/Sidebar.vue', 'src/components/layout/Topbar.vue'],
    rules: {
      'vue/multi-word-component-names': 'off',
    },
  },
  {
    files: ['src/__tests__/**'],
    rules: {
      // Test stubs intentionally use untyped props and multiple components per file
      'vue/require-prop-types': 'off',
      'vue/one-component-per-file': 'off',
    },
  },
]
