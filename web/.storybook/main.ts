import { defineMain } from '@storybook/react-vite/node'

export default defineMain({
  stories: ['../src/**/*.stories.@(ts|tsx)'],
  framework: '@storybook/react-vite',
  addons: [
    '@storybook/addon-docs',
    '@storybook/addon-a11y',
  ],
  async viteFinal(config) {
    const { default: tailwindcss } = await import('@tailwindcss/vite')
    config.plugins = [...(config.plugins ?? []), tailwindcss()]
    // Disable sourcemaps and minification for Storybook builds to avoid
    // rolldown segfault on Linux CI (rolldown 1.0.0-rc.13+, 4200+ modules).
    // Storybook builds are for verification only, not production serving.
    config.build = {
      ...config.build,
      sourcemap: false,
      minify: false,
    }
    return config
  },
})
