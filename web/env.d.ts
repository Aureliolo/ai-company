/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string | undefined
  /**
   * Build identifier baked into the bundle at build time by
   * `vite.config.ts` (defaults to `package.json#version`; CI can
   * override with `SYNTHORG_BUILD_ID`). Consumed by
   * `@/utils/app-version` to gate the post-upgrade stale-cookie
   * recovery flow.
   */
  readonly VITE_APP_BUILD_ID: string | undefined
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
