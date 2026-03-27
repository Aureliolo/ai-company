import { useCallback, useState } from 'react'
import { InputField } from '@/components/ui/input-field'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/stores/auth'
import { useSetupWizardStore } from '@/stores/setup-wizard'
import { getPasswordStrength } from '@/utils/password-strength'
import { cn } from '@/lib/utils'

const MIN_PASSWORD_LENGTH = 12

export function AccountStep() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const authSetup = useAuthStore((s) => s.setup)
  const setAccountCreated = useSetupWizardStore((s) => s.setAccountCreated)
  const markStepComplete = useSetupWizardStore((s) => s.markStepComplete)

  const strength = getPasswordStrength(password)

  const handleSubmit = useCallback(async () => {
    setError(null)
    if (!username.trim()) {
      setError('Username is required')
      return
    }
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters`)
      return
    }
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
  }, [username, password, confirmPassword, authSetup, setAccountCreated, markStepComplete])

  return (
    <div className="mx-auto max-w-md space-y-6">
      <div className="space-y-2">
        <h2 className="text-lg font-semibold text-foreground">Create Admin Account</h2>
        <p className="text-sm text-muted-foreground">
          Set up your administrator account to get started.
        </p>
      </div>

      <div className="space-y-4 rounded-lg border border-border bg-card p-6">
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
            placeholder={`Min ${MIN_PASSWORD_LENGTH} characters`}
            disabled={loading}
            hint={`Min ${MIN_PASSWORD_LENGTH} characters`}
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
          <div role="alert" className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
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
