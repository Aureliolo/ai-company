/** Password strength assessment for the setup wizard. */

export interface PasswordStrength {
  readonly label: string
  readonly percent: number
  readonly color: string
}

const EMPTY: PasswordStrength = { label: '', percent: 0, color: 'bg-border' }

export function getPasswordStrength(password: string): PasswordStrength {
  if (password.length === 0) return EMPTY
  if (password.length < 8) return { label: 'Weak', percent: 20, color: 'bg-danger' }
  if (password.length < 12) return { label: 'Fair', percent: 40, color: 'bg-warning' }
  const hasUpper = /[A-Z]/.test(password)
  const hasLower = /[a-z]/.test(password)
  const hasDigit = /\d/.test(password)
  const hasSpecial = /[^A-Za-z0-9]/.test(password)
  const variety = [hasUpper, hasLower, hasDigit, hasSpecial].filter(Boolean).length
  if (variety >= 3 && password.length >= 16) return { label: 'Strong', percent: 100, color: 'bg-success' }
  if (variety >= 3) return { label: 'Good', percent: 75, color: 'bg-accent' }
  return { label: 'Fair', percent: 50, color: 'bg-warning' }
}
