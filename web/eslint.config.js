import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import eslintReact from '@eslint-react/eslint-plugin'
import { reactRefresh } from 'eslint-plugin-react-refresh'
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
      'react-refresh': reactRefresh.plugin,
    },
    rules: {
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
      'no-useless-assignment': 'error',
      'no-restricted-syntax': [
        'error',
        {
          selector: 'JSXAttribute[name.name="dangerouslySetInnerHTML"]',
          message:
            'dangerouslySetInnerHTML is banned -- use text content or a sanitization library. ' +
            'If absolutely necessary, add // eslint-disable-next-line no-restricted-syntax with a justification comment.',
        },
      ],
      // Rule flags every obj[var] with no data-flow analysis -- too many false
      // positives. Prototype pollution is guarded explicitly at system boundaries.
      'security/detect-object-injection': 'off',
      // -- eslint-react rules not in recommended-typescript --
      // Prevent dollar signs from leaking into rendered JSX output
      '@eslint-react/jsx-no-leaked-dollar': 'error',
      // Remove unnecessary <></> fragment wrappers
      '@eslint-react/jsx-no-useless-fragment': 'warn',
      // Require type attribute on <button> to prevent unintended form submission
      '@eslint-react/dom-no-missing-button-type': 'warn',
      // Require rel="noopener" with target="_blank" (security)
      '@eslint-react/dom-no-unsafe-target-blank': 'error',
      // Catch duplicate keys in JSX lists
      '@eslint-react/no-duplicate-key': 'error',
      // Catch unstable context values that cause unnecessary re-renders
      '@eslint-react/no-unstable-context-value': 'warn',
      // Catch unstable default props that cause unnecessary re-renders
      '@eslint-react/no-unstable-default-props': 'warn',
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
