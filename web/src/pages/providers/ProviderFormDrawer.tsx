import { useCallback, useEffect, useState } from 'react'
import { Drawer } from '@/components/ui/drawer'
import { InputField } from '@/components/ui/input-field'
import { SelectField } from '@/components/ui/select-field'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { PresetPicker } from './PresetPicker'
import { useProvidersStore } from '@/stores/providers'
import type { AuthType, ProviderPreset } from '@/api/types'
import type { ProviderWithName } from '@/utils/providers'

const AUTH_OPTIONS: { value: AuthType; label: string }[] = [
  { value: 'api_key', label: 'API Key' },
  { value: 'subscription', label: 'Subscription (OAuth)' },
  { value: 'none', label: 'None' },
]

interface ProviderFormDrawerProps {
  open: boolean
  onClose: () => void
  mode: 'create' | 'edit'
  provider?: ProviderWithName | null
}

export function ProviderFormDrawer({
  open,
  onClose,
  mode,
  provider,
}: ProviderFormDrawerProps) {
  const presets = useProvidersStore((s) => s.presets)
  const presetsLoading = useProvidersStore((s) => s.presetsLoading)
  const presetsError = useProvidersStore((s) => s.presetsError)

  // Form state
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [authType, setAuthType] = useState<AuthType>('api_key')
  const [apiKey, setApiKey] = useState('')
  const [subscriptionToken, setSubscriptionToken] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [litellmProvider, setLitellmProvider] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // ToS dialog
  const [showTosDialog, setShowTosDialog] = useState(false)
  const [tosAccepted, setTosAccepted] = useState(false)

  // Resolve selected preset
  const preset: ProviderPreset | undefined = presets.find((p) => p.name === selectedPreset)
  const isCustom = selectedPreset === '__custom__'

  // Fetch presets when drawer opens in create mode
  useEffect(() => {
    if (open && mode === 'create') {
      useProvidersStore.getState().fetchPresets()
    }
  }, [open, mode])

  // Pre-fill in edit mode
  useEffect(() => {
    if (mode === 'edit' && provider) {
      setName(provider.name)
      setAuthType(provider.auth_type)
      setBaseUrl(provider.base_url ?? '')
      setLitellmProvider(provider.litellm_provider ?? '')
      setTosAccepted(provider.tos_accepted_at !== null)
    }
  }, [mode, provider])

  // When preset changes, auto-fill form fields (or reset for custom)
  useEffect(() => {
    if (selectedPreset === '__custom__') {
      setName('')
      setAuthType('api_key')
      setApiKey('')
      setSubscriptionToken('')
      setBaseUrl('')
      setLitellmProvider('')
      setTosAccepted(false)
      return
    }
    if (!preset) return
    setName(preset.name)
    setAuthType(preset.auth_type)
    setBaseUrl(preset.default_base_url ?? '')
    setLitellmProvider(preset.litellm_provider)
    setTosAccepted(false)
    setSubscriptionToken('')
    setApiKey('')
  }, [preset, selectedPreset])

  // Available auth types based on selected preset
  const availableAuthTypes = preset
    ? AUTH_OPTIONS.filter((opt) => preset.supported_auth_types.includes(opt.value))
    : AUTH_OPTIONS

  const handleAuthTypeChange = useCallback((value: string) => {
    const newType = value as AuthType
    setAuthType(newType)
    if (newType === 'subscription' && !tosAccepted) {
      setShowTosDialog(true)
    }
  }, [tosAccepted])

  const resetForm = useCallback(() => {
    setSelectedPreset(null)
    setName('')
    setAuthType('api_key')
    setApiKey('')
    setSubscriptionToken('')
    setBaseUrl('')
    setLitellmProvider('')
    setSubmitting(false)
    setTosAccepted(false)
  }, [])

  // Reset form when mode switches (e.g., edit -> create without closing)
  useEffect(() => {
    if (mode === 'create' && open) resetForm()
  }, [mode, open, resetForm])

  const handleClose = useCallback(() => {
    resetForm()
    onClose()
  }, [resetForm, onClose])

  const handleSubmit = useCallback(async () => {
    setSubmitting(true)

    try {
      if (mode === 'create') {
        if (preset && selectedPreset !== '__custom__') {
          const result = await useProvidersStore.getState().createFromPreset({
            preset_name: preset.name,
            name: name.trim(),
            auth_type: authType,
            api_key: authType === 'api_key' && apiKey ? apiKey : undefined,
            subscription_token: authType === 'subscription' && subscriptionToken ? subscriptionToken : undefined,
            tos_accepted: authType === 'subscription' && tosAccepted,
            base_url: baseUrl || undefined,
          })
          if (result) handleClose()
        } else {
          const result = await useProvidersStore.getState().createProvider({
            name: name.trim(),
            litellm_provider: litellmProvider || undefined,
            auth_type: authType,
            api_key: authType === 'api_key' && apiKey ? apiKey : undefined,
            subscription_token: authType === 'subscription' && subscriptionToken ? subscriptionToken : undefined,
            tos_accepted: authType === 'subscription' && tosAccepted,
            base_url: baseUrl || undefined,
          })
          if (result) handleClose()
        }
      } else if (mode === 'edit' && provider) {
        const result = await useProvidersStore.getState().updateProvider(provider.name, {
          litellm_provider: litellmProvider || undefined,
          auth_type: authType,
          api_key: authType === 'api_key' && apiKey ? apiKey : undefined,
          clear_api_key: authType !== 'api_key' || !apiKey,
          subscription_token: authType === 'subscription' && subscriptionToken ? subscriptionToken : undefined,
          clear_subscription_token: authType !== 'subscription' || !subscriptionToken,
          tos_accepted: authType === 'subscription' && tosAccepted,
          base_url: baseUrl || undefined,
        })
        if (result) handleClose()
      }
    } finally {
      setSubmitting(false)
    }
  }, [mode, preset, selectedPreset, name, authType, apiKey, subscriptionToken, tosAccepted, baseUrl, litellmProvider, provider, handleClose])

  return (
    <>
      <Drawer
        open={open}
        onClose={handleClose}
        title={mode === 'create' ? 'Add Provider' : `Edit ${provider?.name ?? 'Provider'}`}
      >
        <div className="flex flex-col gap-6 p-4">
          {/* Presets error banner */}
          {presetsError && (
            <div className="rounded-md bg-danger/10 px-4 py-3 text-sm text-danger">
              Failed to load provider presets: {presetsError}
            </div>
          )}

          {/* Step 1: Preset picker (create only) */}
          {mode === 'create' && (
            <div>
              <h3 className="mb-3 text-sm font-medium text-foreground">
                Select Provider Type
              </h3>
              <PresetPicker
                presets={presets}
                selected={selectedPreset}
                onSelect={setSelectedPreset}
                loading={presetsLoading}
              />
            </div>
          )}

          {/* Step 2+: Configuration (shown after preset selected or in edit mode) */}
          {(selectedPreset !== null || mode === 'edit') && (
            <>
              {/* Auth type */}
              <SelectField
                label="Authentication"
                options={availableAuthTypes}
                value={authType}
                onChange={handleAuthTypeChange}
              />

              {/* Auth-specific fields */}
              {authType === 'api_key' && (
                <InputField
                  label="API Key"
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={mode === 'edit' && provider?.has_api_key ? '(unchanged)' : 'sk-...'}
                  hint={mode === 'edit' ? 'Leave empty to keep existing key' : undefined}
                />
              )}

              {authType === 'subscription' && (
                <>
                  {!tosAccepted && (
                    <div className="rounded-md border border-warning/30 bg-warning/5 p-3 text-xs text-text-secondary">
                      You must accept the Terms of Service warning before using subscription auth.
                      <Button
                        variant="outline"
                        size="sm"
                        className="ml-2"
                        onClick={() => setShowTosDialog(true)}
                      >
                        Review & Accept
                      </Button>
                    </div>
                  )}
                  {tosAccepted && (
                    <InputField
                      label="Subscription Token"
                      type="password"
                      value={subscriptionToken}
                      onChange={(e) => setSubscriptionToken(e.target.value)}
                      placeholder="sub-token-..."
                      hint="Run 'claude setup-token' in your terminal to get this token"
                    />
                  )}
                </>
              )}

              {/* Provider name */}
              <InputField
                label="Provider Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="my-provider"
                hint="Lowercase, alphanumeric + hyphens"
                disabled={mode === 'edit'}
              />

              {/* Base URL */}
              {(isCustom || preset != null || mode === 'edit') && (
                <InputField
                  label="Base URL"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder={preset?.default_base_url ?? 'https://api.example.com/v1'}
                  hint={
                    isCustom || mode === 'edit'
                      ? undefined
                      : preset && !preset.default_base_url
                        ? 'Required for this provider'
                        : !preset?.default_base_url
                          ? 'Optional for known cloud providers'
                          : undefined
                  }
                />
              )}

              {/* LiteLLM Provider (custom only) */}
              {(isCustom || mode === 'edit') && (
                <InputField
                  label="LiteLLM Provider"
                  value={litellmProvider}
                  onChange={(e) => setLitellmProvider(e.target.value)}
                  placeholder="anthropic, openai, ollama..."
                  hint="LiteLLM routing identifier for model name prefixing"
                />
              )}

              {/* Submit */}
              <div className="flex justify-end gap-3 pt-2">
                <Button variant="outline" onClick={handleClose} disabled={submitting}>
                  Cancel
                </Button>
                <Button
                  onClick={handleSubmit}
                  disabled={submitting || !name.trim() || (authType === 'subscription' && !tosAccepted)}
                >
                  {submitting ? 'Saving...' : mode === 'create' ? 'Create Provider' : 'Save Changes'}
                </Button>
              </div>
            </>
          )}
        </div>
      </Drawer>

      {/* Subscription ToS Dialog */}
      <ConfirmDialog
        open={showTosDialog}
        onOpenChange={setShowTosDialog}
        title="Subscription Authentication"
        description="Using subscription OAuth tokens in third-party applications may not be permitted by the provider's Terms of Service. This feature is provided as-is, with no guarantees of continued availability. You are responsible for ensuring your usage complies with the provider's terms."
        confirmLabel="I Understand & Accept"
        cancelLabel="Cancel"
        onConfirm={() => {
          setTosAccepted(true)
          setShowTosDialog(false)
        }}
      />
    </>
  )
}
