export function DependencyMissingBanner() {
  return (
    <div className="rounded-lg border border-danger/30 bg-danger/5 p-card" role="alert">
      <h3 className="text-sm font-medium text-danger">
        Fine-tuning not enabled for this install
      </h3>
      <p className="mt-1 text-sm text-muted-foreground">
        The backend reports that PyTorch and sentence-transformers are
        unavailable. In a Docker-orchestrated install these ship inside the{' '}
        <code className="font-mono">synthorg-fine-tune-gpu</code> or{' '}
        <code className="font-mono">synthorg-fine-tune-cpu</code> container,
        which the backend spawns on demand. Enable it without wiping your
        install:
      </p>
      <code className="mt-2 block rounded bg-muted px-3 py-2 font-mono text-xs text-foreground">
        synthorg config set sandbox true
        <br />
        synthorg config set fine_tuning true
        <br />
        synthorg config set fine_tuning_variant gpu {'  '}# or: cpu
        <br />
        synthorg stop &amp;&amp; synthorg start
      </code>
      <p className="mt-2 text-sm text-muted-foreground">
        Running a hand-managed <code className="font-mono">compose.yml</code>{' '}
        without the CLI? See the{' '}
        <a
          className="text-accent underline underline-offset-2 hover:no-underline"
          href="https://synthorg.io/docs/guides/deployment/#fine-tuning-optional"
          target="_blank"
          rel="noreferrer"
        >
          Fine-Tuning section of the Deployment guide
        </a>{' '}
        for the BYO-compose snippet.
      </p>
    </div>
  )
}
