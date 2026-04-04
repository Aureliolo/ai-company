import { sanitizeForLog } from '@/utils/logging'

/** Structured logger returned by {@link createLogger}. */
export interface Logger {
  /** Debug-level log, only emitted in development builds. */
  debug(message: string, ...args: unknown[]): void
  warn(message: string, ...args: unknown[]): void
  error(message: string, ...args: unknown[]): void
}

function sanitizeArg(value: unknown): unknown {
  if (typeof value === 'string') return sanitizeForLog(value)
  if (value instanceof Error) return sanitizeForLog(value)
  // Structured objects pass through for devtools inspection
  if (value !== null && typeof value === 'object') return value
  // Sanitize other primitives (numbers pass through String() harmlessly,
  // but null/undefined/boolean/symbol get consistent treatment)
  return sanitizeForLog(value)
}

/**
 * Create a module-scoped logger that prefixes messages with `[module]`
 * and automatically sanitizes string/Error arguments via `sanitizeForLog`.
 *
 * Structured objects are passed through unchanged so devtools can inspect them.
 */
export function createLogger(module: string): Logger {
  const prefix = `[${module}]`
  return {
    debug(message: string, ...args: unknown[]) {
      if (import.meta.env.DEV) {
        console.debug(prefix, message, ...args.map(sanitizeArg))
      }
    },
    warn(message: string, ...args: unknown[]) {
      console.warn(prefix, message, ...args.map(sanitizeArg))
    },
    error(message: string, ...args: unknown[]) {
      console.error(prefix, message, ...args.map(sanitizeArg))
    },
  }
}
