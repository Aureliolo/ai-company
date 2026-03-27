import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router'
import { InputField } from '@/components/ui/input-field'
import { Button } from '@/components/ui/button'
import { useSetupWizardStore } from '@/stores/setup-wizard'
import { useSetupStore } from '@/stores/setup'
import { useToastStore } from '@/stores/toast'

export function SkipWizardForm() {
  const navigate = useNavigate()
  const [companyName, setCompanyName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const submitCompany = useSetupWizardStore((s) => s.submitCompany)
  const setCompanyNameStore = useSetupWizardStore((s) => s.setCompanyName)
  const wizardCompleteSetup = useSetupWizardStore((s) => s.completeSetup)

  const handleSubmit = useCallback(async () => {
    const trimmed = companyName.trim()
    if (!trimmed) {
      setError('Company name is required')
      return
    }
    setLoading(true)
    setError(null)
    try {
      setCompanyNameStore(trimmed)
      await submitCompany()
      const companyErr = useSetupWizardStore.getState().companyError
      if (companyErr) {
        setError(companyErr)
        return
      }
      await wizardCompleteSetup()
      const completionErr = useSetupWizardStore.getState().completionError
      if (completionErr) {
        setError(completionErr)
        return
      }
      useSetupStore.setState({ setupComplete: true })
      useToastStore.getState().add({
        variant: 'success',
        title: `Welcome to ${trimmed}!`,
        description: 'Setup complete. Configure everything else in Settings.',
      })
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Setup failed')
    } finally {
      setLoading(false)
    }
  }, [companyName, setCompanyNameStore, submitCompany, wizardCompleteSetup, navigate])

  return (
    <div className="mx-auto max-w-md space-y-6">
      <div className="space-y-2">
        <h2 className="text-lg font-semibold text-foreground">Quick Setup</h2>
        <p className="text-sm text-muted-foreground">
          Skip the wizard and configure everything later in Settings.
        </p>
      </div>

      <div className="space-y-4 rounded-lg border border-border bg-card p-6">
        <InputField
          label="Company Name"
          required
          value={companyName}
          onChange={(e) => setCompanyName(e.currentTarget.value)}
          placeholder="Your organization name"
          disabled={loading}
        />

        {error && (
          <div role="alert" className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
            {error}
          </div>
        )}

        <Button onClick={handleSubmit} disabled={loading} className="w-full">
          {loading ? 'Setting up...' : 'Complete Setup'}
        </Button>
      </div>
    </div>
  )
}
