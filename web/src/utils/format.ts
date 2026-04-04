/** Formatting utilities for dates, currency, and numbers. */

import { createLogger } from '@/lib/logger'

const log = createLogger('format')

/**
 * Format an ISO 8601 date string to a human-readable locale string.
 */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '--'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '--'
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Format a date as relative time (e.g., "2 hours ago").
 */
export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return '--'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '--'
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  if (diffMs < 0) return formatDate(iso)
  const diffSec = Math.floor(diffMs / 1000)

  if (diffSec < 60) return 'just now'
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`
  if (diffSec < 604800) return `${Math.floor(diffSec / 86400)}d ago`
  return formatDate(iso)
}

/** ISO 4217 currencies that use zero decimal places. */
const ZERO_DECIMAL_CURRENCIES = new Set(['BIF','CLP','DJF','GNF','HUF','ISK','JPY','KMF','KRW','MGA','PYG','RWF','UGX','VND','VUV','XAF','XOF','XPF'])

/** ISO 4217 currencies that use three decimal places. */
const THREE_DECIMAL_CURRENCIES = new Set(['BHD','IQD','JOD','KWD','LYD','OMR','TND'])

/**
 * Format a currency value using the given ISO 4217 currency code.
 */
export function formatCurrency(value: number, currencyCode: string = 'EUR'): string {
  if (!Number.isFinite(value)) return '--'
  try {
    return new Intl.NumberFormat('en-US', {
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
export function formatCurrencyCompact(value: number, currencyCode: string = 'EUR'): string {
  if (!Number.isFinite(value)) return '--'
  // Normalize to 3-letter uppercase ISO 4217 code; fall back to EUR
  const trimmed = currencyCode.trim()
  const code = /^[A-Za-z]{3}$/.test(trimmed) ? trimmed.toUpperCase() : 'EUR'
  try {
    return new Intl.NumberFormat('en-US', {
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
export function formatNumber(value: number): string {
  if (!Number.isFinite(value)) return '--'
  return new Intl.NumberFormat('en-US').format(value)
}

/**
 * Format seconds as a human-readable uptime string.
 */
export function formatUptime(seconds: number): string {
  const s = (!Number.isFinite(seconds) || seconds < 0) ? 0 : seconds
  const days = Math.floor(s / 86400)
  const hours = Math.floor((s % 86400) / 3600)
  const mins = Math.floor((s % 3600) / 60)
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
  const exponent = Math.max(0, Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1))
  const value = bytes / 1024 ** exponent
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
