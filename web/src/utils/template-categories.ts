/** Template categorization for the setup wizard. */

import type { TemplateInfoResponse } from '@/api/types'

/**
 * Known category tags mapped to display labels.
 * Templates are categorized by the first tag that matches a known category.
 */
const CATEGORY_LABELS: Readonly<Record<string, string>> = {
  startup: 'Startup',
  solo: 'Startup',
  'small-team': 'Startup',
  mvp: 'Startup',
  'dev-shop': 'Development',
  'data-team': 'Development',
  product: 'Product',
  agile: 'Product',
  enterprise: 'Enterprise',
  'full-company': 'Enterprise',
  consultancy: 'Professional Services',
  agency: 'Professional Services',
  research: 'Research',
}

/**
 * Reverse mapping: display label to canonical category key.
 * Used to group templates by display category.
 */
const LABEL_TO_CATEGORY: Readonly<Record<string, string>> = {
  Startup: 'startup',
  Development: 'dev-shop',
  Product: 'product',
  Enterprise: 'enterprise',
  'Professional Services': 'consultancy',
  Research: 'research',
  Other: 'other',
}

/** Ordered list of category keys for display. */
export const CATEGORY_ORDER: readonly string[] = [
  'startup',
  'dev-shop',
  'product',
  'enterprise',
  'consultancy',
  'research',
  'other',
]

/**
 * Get the canonical category key for a template based on its tags.
 * Returns the first matching category, or 'other' if no match.
 */
function getTemplateCategory(template: TemplateInfoResponse): string {
  for (const tag of template.tags) {
    const label = CATEGORY_LABELS[tag]
    if (label) {
      return LABEL_TO_CATEGORY[label] ?? 'other'
    }
  }
  return 'other'
}

/**
 * Group templates into ordered categories based on their tags.
 *
 * Returns a Map with category keys in CATEGORY_ORDER.
 * Categories with no templates are omitted.
 */
export function categorizeTemplates(
  templates: readonly TemplateInfoResponse[],
): Map<string, TemplateInfoResponse[]> {
  const groups = new Map<string, TemplateInfoResponse[]>()

  for (const template of templates) {
    const category = getTemplateCategory(template)
    const existing = groups.get(category)
    if (existing) {
      existing.push(template)
    } else {
      groups.set(category, [template])
    }
  }

  // Reorder to match CATEGORY_ORDER
  const ordered = new Map<string, TemplateInfoResponse[]>()
  for (const key of CATEGORY_ORDER) {
    const items = groups.get(key)
    if (items) {
      ordered.set(key, items)
    }
  }

  // Add any categories not in CATEGORY_ORDER at the end
  for (const [key, items] of groups) {
    if (!ordered.has(key)) {
      ordered.set(key, items)
    }
  }

  return ordered
}

/**
 * Get a human-readable label for a category key.
 */
export function getCategoryLabel(category: string): string {
  // Check if this category key has a known label
  for (const [label, key] of Object.entries(LABEL_TO_CATEGORY)) {
    if (key === category) return label
  }
  // Title-case the key as fallback
  return category.charAt(0).toUpperCase() + category.slice(1)
}
