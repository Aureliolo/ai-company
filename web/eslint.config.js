import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import eslintReact from '@eslint-react/eslint-plugin'
import reactRefresh from 'eslint-plugin-react-refresh'
import pluginSecurity from 'eslint-plugin-security'

// TODO: Add eslint-plugin-react-hooks when it supports ESLint 10 (v5 caps at ESLint 9).
// @eslint-react provides some hooks analysis via hooks-extra rules in the meantime.

export default tseslint.config(
  { ignores: ['dist/**'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  eslintReact.configs['recommended-typescript'],
  pluginSecurity.configs.recommended,
  {
    plugins: {
      'react-refresh': reactRefresh,
    },
    rules: {
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
      'no-useless-assignment': 'error',
      // Rule flags every obj[var] with no data-flow analysis -- too many false
      // positives. Prototype pollution is guarded explicitly at system boundaries.
      'security/detect-object-injection': 'off',
    },
  },
  {
    // shadcn/ui components co-export variant helpers alongside components --
    // this is the standard pattern and safe for HMR.
    files: ['src/components/ui/**'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
)
