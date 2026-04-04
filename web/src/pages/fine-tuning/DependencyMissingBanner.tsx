export function DependencyMissingBanner() {
  return (
    <div className="rounded-lg border border-danger/30 bg-danger/5 p-card" role="alert">
      <h3 className="text-sm font-medium text-danger">
        Fine-tuning dependencies not installed
      </h3>
      <p className="mt-1 text-sm text-muted-foreground">
        The fine-tuning pipeline requires PyTorch and sentence-transformers.
        Install them with:
      </p>
      <code className="mt-2 block rounded bg-muted px-3 py-2 font-mono text-xs text-foreground">
        pip install synthorg[fine-tune]
      </code>
    </div>
  )
}
