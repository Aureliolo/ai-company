/** Formatting utilities for dates, currency, and numbers. */

import { createLogger } from '@/lib/logger'
import { getLocale } from '@/utils/locale'

const log = createLogger('format')

const MS_PER_SECOND = 1000
const SEC_PER_MIN = 60
const SEC_PER_HOUR = 3600
const SEC_PER_DAY = 86400
const SEC_PER_WEEK = 604800
const BYTES_PER_KB = 1024
const COMPACT_K_THRESHOLD = 1000

/**
 * Format an ISO 8601 date string as date + time (e.g. "Jan 15, 2025, 10:30 AM").
 */
export function formatDateTime(
  iso: string | null | undefined,
  locale: string = getLocale(),
): string {
  if (!iso) return '--'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '--'
  return date.toLocaleString(locale, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Alias of {@link formatDateTime} kept for the existing call sites that
 * import `formatDate`. New code should prefer `formatDateTime` for
 * clarity or `formatDateOnly` when no time is needed.
 */
export const formatDate = formatDateTime

/**
 * Format an ISO 8601 date as a date-only string (e.g. "Jan 15, 2025").
 */
export function formatDateOnly(
  iso: string | null | undefined,
  locale: string = getLocale(),
): string {
  if (!iso) return '--'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '--'
  return date.toLocaleDateString(locale, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

/**
 * Format an ISO 8601 date as a time-only string (e.g. "10:30 AM").
 */
export function formatTime(
  iso: string | null | undefined,
  locale: string = getLocale(),
): string {
  if (!iso) return '--'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '--'
  return date.toLocaleTimeString(locale, {
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Format a short day label for chart axes (e.g. "Jan 15").
 *
 * Accepts either an ISO string, a `Date`, or a millisecond timestamp.
 */
export function formatDayLabel(
  value: string | number | Date,
  locale: string = getLocale(),
): string {
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return '--'
  return date.toLocaleDateString(locale, { month: 'short', day: 'numeric' })
}

/**
 * Format today's short day label (e.g. "Jan 15"). Useful as a reference
 * line label on burn/trend charts.
 */
export function formatTodayLabel(locale: string = getLocale()): string {
  return formatDayLabel(new Date(), locale)
}

/**
 * Format a date as relative time (e.g., "2 hours ago").
 */
export function formatRelativeTime(
  iso: string | null | undefined,
  locale: string = getLocale(),
): string {
  if (!iso) return '--'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '--'
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  if (diffMs < 0) return formatDateTime(iso, locale)
  const diffSec = Math.floor(diffMs / MS_PER_SECOND)

  if (diffSec < SEC_PER_MIN) return 'just now'
  if (diffSec < SEC_PER_HOUR) return `${Math.floor(diffSec / SEC_PER_MIN)}m ago`
  if (diffSec < SEC_PER_DAY) return `${Math.floor(diffSec / SEC_PER_HOUR)}h ago`
  if (diffSec < SEC_PER_WEEK) return `${Math.floor(diffSec / SEC_PER_DAY)}d ago`
  return formatDateTime(iso, locale)
}

/** ISO 4217 currencies that use zero decimal places. */
const ZERO_DECIMAL_CURRENCIES = new Set(['BIF','CLP','DJF','GNF','HUF','ISK','JPY','KMF','KRW','MGA','PYG','RWF','UGX','VND','VUV','XAF','XOF','XPF'])

/** ISO 4217 currencies that use three decimal places. */
const THREE_DECIMAL_CURRENCIES = new Set(['BHD','IQD','JOD','KWD','LYD','OMR','TND'])

/**
 * Format a currency value using the given ISO 4217 currency code.
 */
export function formatCurrency(
  value: number,
  currencyCode: string = 'EUR',
  locale: string = getLocale(),
): string {
  if (!Number.isFinite(value)) return '--'
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: currencyCode,
    }).format(value)
  } catch (error) {
    log.error('Intl.NumberFormat failed for currency:', currencyCode, error)
    const digits = ZERO_DECIMAL_CURRENCIES.has(currencyCode) ? 0 : THREE_DECIMAL_CURRENCIES.has(currencyCode) ? 3 : 2
    return `${currencyCode} ${value.toFixed(digits)}`
  }
}

/**
 * Format a currency value compactly for chart axes (e.g. "$5", "$10K").
 * Exact format depends on locale and currency. Falls back to "CODE N" on error.
 */
export function formatCurrencyCompact(
  value: number,
  currencyCode: string = 'EUR',
  locale: string = getLocale(),
): string {
  if (!Number.isFinite(value)) return '--'
  // Normalize to 3-letter uppercase ISO 4217 code; fall back to EUR
  const trimmed = currencyCode.trim()
  const code = /^[A-Za-z]{3}$/.test(trimmed) ? trimmed.toUpperCase() : 'EUR'
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: code,
      maximumFractionDigits: 0,
      notation: 'compact',
    }).format(value)
  } catch (error) {
    log.error(`Intl.NumberFormat compact failed for currency "${code}":`, error)
    return `${code} ${Math.round(value)}`
  }
}

/**
 * Format a number with locale-appropriate separators.
 */
export function formatNumber(
  value: number,
  locale: string = getLocale(),
): string {
  if (!Number.isFinite(value)) return '--'
  return new Intl.NumberFormat(locale).format(value)
}

/**
 * Format a count of tokens for display. Values under 1000 use
 * locale-appropriate separators (typically just the number); larger
 * values use compact notation (e.g. "12K", "1.5M").
 */
export function formatTokenCount(
  value: number,
  locale: string = getLocale(),
): string {
  if (!Number.isFinite(value)) return '--'
  if (value < COMPACT_K_THRESHOLD) return formatNumber(value, locale)
  return new Intl.NumberFormat(locale, {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value)
}

/**
 * Format seconds as a human-readable uptime string.
 */
export function formatUptime(seconds: number): string {
  const s = (!Number.isFinite(seconds) || seconds < 0) ? 0 : seconds
  const days = Math.floor(s / SEC_PER_DAY)
  const hours = Math.floor((s % SEC_PER_DAY) / SEC_PER_HOUR)
  const mins = Math.floor((s % SEC_PER_HOUR) / SEC_PER_MIN)
  const parts: string[] = []
  if (days > 0) parts.push(`${days}d`)
  if (hours > 0) parts.push(`${hours}h`)
  if (mins > 0 || parts.length === 0) parts.push(`${mins}m`)
  return parts.join(' ')
}

/**
 * Format a byte count to a human-readable size string (e.g. "1.2 MB").
 */
export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '--'
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const exponent = Math.max(0, Math.min(Math.floor(Math.log(bytes) / Math.log(BYTES_PER_KB)), units.length - 1))
  const value = bytes / BYTES_PER_KB ** exponent
  return exponent === 0 ? `${bytes} B` : `${value.toFixed(1)} ${units[exponent]}`
}

/**
 * Capitalize and format a snake_case or kebab-case string for display.
 */
export function formatLabel(value: string): string {
  return value
    .split(/[_-]/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}
