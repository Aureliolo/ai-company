import { useCallback, useEffect, useState } from 'react'
import { createLogger } from '@/lib/logger'
import { InputField } from '@/components/ui/input-field'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/stores/auth'
import { useSetupWizardStore } from '@/stores/setup-wizard'
import { getPasswordStrength } from '@/utils/password-strength'
import { getSetupStatus } from '@/api/endpoints/setup'
import { cn } from '@/lib/utils'

const log = createLogger('setup')

const DEFAULT_MIN_PASSWORD_LENGTH = 12

export function AccountStep() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [minPasswordLength, setMinPasswordLength] = useState(DEFAULT_MIN_PASSWORD_LENGTH)

  const authSetup = useAuthStore((s) => s.setup)
  const setAccountCreated = useSetupWizardStore((s) => s.setAccountCreated)
  const markStepComplete = useSetupWizardStore((s) => s.markStepComplete)

  // Read backend-configured min password length
  useEffect(() => {
    getSetupStatus()
      .then((status) => {
        setMinPasswordLength(
          status.min_password_length ?? DEFAULT_MIN_PASSWORD_LENGTH,
        )
      })
      .catch((err) => {
        log.error('Failed to fetch setup status:', err)
      })
  }, [])

  const strength = getPasswordStrength(password)

  const handleSubmit = useCallback(async () => {
    setError(null)
    if (!username.trim()) {
      setError('Username is required')
      return
    }
    if (password.length < minPasswordLength) {
      setError(`Password must be at least ${minPasswordLength} characters`)
      return
    }
    // eslint-disable-next-line security/detect-possible-timing-attacks -- client-side UI validation of user's own input
    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    setLoading(true)
    try {
      await authSetup(username.trim(), password)
      setAccountCreated(true)
      markStepComplete('account')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create account')
    } finally {
      setLoading(false)
    }
  }, [username, password, confirmPassword, minPasswordLength, authSetup, setAccountCreated, markStepComplete])

  return (
    <div className="mx-auto max-w-md space-y-section-gap">
      <div className="space-y-2">
        <h2 className="text-lg font-semibold text-foreground">Create Admin Account</h2>
        <p className="text-sm text-muted-foreground">
          Set up your administrator account to get started.
        </p>
      </div>

      <div className="space-y-4 rounded-lg border border-border bg-card p-card">
        <InputField
          label="Username"
          required
          value={username}
          onChange={(e) => setUsername(e.currentTarget.value)}
          placeholder="admin"
          disabled={loading}
        />

        <div className="space-y-1.5">
          <InputField
            label="Password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.currentTarget.value)}
            placeholder={`Min ${minPasswordLength} characters`}
            disabled={loading}
            hint={`Min ${minPasswordLength} characters`}
          />
          {password.length > 0 && (
            <div className="flex items-center gap-2">
              <div className="h-1.5 flex-1 rounded-full bg-border">
                <div
                  className={cn('h-full rounded-full transition-all', strength.color)}
                  style={{ width: `${strength.percent}%` }}
                />
              </div>
              <span className="text-compact text-muted-foreground">{strength.label}</span>
            </div>
          )}
        </div>

        <InputField
          label="Confirm Password"
          type="password"
          required
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.currentTarget.value)}
          placeholder="Repeat password"
          disabled={loading}
          error={confirmPassword.length > 0 && password !== confirmPassword ? 'Passwords do not match' : null}
        />

        {error && (
          <div role="alert" className="rounded-md border border-danger/30 bg-danger/5 p-card text-sm text-danger">
            {error}
          </div>
        )}

        <Button onClick={handleSubmit} disabled={loading} className="w-full">
          {loading ? 'Creating Account...' : 'Create Account'}
        </Button>
      </div>
    </div>
  )
}
