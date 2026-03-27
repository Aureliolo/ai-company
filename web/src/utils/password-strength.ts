/** Password strength assessment for the setup wizard. */

export interface PasswordStrength {
  readonly label: string
  readonly percent: number
  readonly color: string
}

/** Minimum length before a password is considered anything above "Weak". */
const WEAK_THRESHOLD = 8
/** Minimum length for a "Fair" rating (below this with >= WEAK_THRESHOLD is also "Fair"). */
const FAIR_THRESHOLD = 12
/** Minimum length for the "Strong" rating (requires sufficient variety too). */
const STRONG_THRESHOLD = 16
/** Minimum number of character categories (upper, lower, digit, special) for "Good"/"Strong". */
const MIN_VARIETY = 3

const EMPTY: PasswordStrength = { label: '', percent: 0, color: 'bg-border' }

export function getPasswordStrength(password: string): PasswordStrength {
  if (password.length === 0) return EMPTY
  if (password.length < WEAK_THRESHOLD) return { label: 'Weak', percent: 20, color: 'bg-danger' }
  if (password.length < FAIR_THRESHOLD) return { label: 'Fair', percent: 40, color: 'bg-warning' }
  const hasUpper = /[A-Z]/.test(password)
  const hasLower = /[a-z]/.test(password)
  const hasDigit = /\d/.test(password)
  const hasSpecial = /[^A-Za-z0-9]/.test(password)
  const variety = [hasUpper, hasLower, hasDigit, hasSpecial].filter(Boolean).length
  if (variety >= MIN_VARIETY && password.length >= STRONG_THRESHOLD) return { label: 'Strong', percent: 100, color: 'bg-success' }
  if (variety >= MIN_VARIETY) return { label: 'Good', percent: 75, color: 'bg-accent' }
  return { label: 'Fair', percent: 50, color: 'bg-warning' }
}
