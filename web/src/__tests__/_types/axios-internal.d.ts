/**
 * Type augmentation for the undocumented ``handlers`` array on axios's
 * interceptor managers. Used by tests that need to inspect the
 * registered interceptor functions to assert wiring without spinning up
 * a real HTTP cycle. This deliberately mirrors the shape used at
 * runtime in axios 1.x; if axios renames or reshapes the field a single
 * test will fail loudly with a typed error rather than a runtime
 * ``undefined`` access.
 */
import 'axios'

declare module 'axios' {
  interface AxiosInterceptorManager<V> {
    handlers?: Array<{
      fulfilled?: (value: V) => V | Promise<V>
      rejected?: (error: unknown) => unknown
    } | null>
  }
}
