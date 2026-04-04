import type { FineTuneStage } from '@/api/endpoints/fine-tuning'

interface PipelineProgressBarProps {
  stage: FineTuneStage
  progress: number | null
}

export function PipelineProgressBar({ stage, progress }: PipelineProgressBarProps) {
  const rawPct = progress != null ? Math.round(progress * 100) : 0
  const pct = Math.min(100, Math.max(0, rawPct))

  return (
    <div className="flex flex-col gap-2 pt-4">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">
          Stage: <span className="font-medium text-foreground">{formatStage(stage)}</span>
        </span>
        <span className="font-mono text-foreground">{pct}%</span>
      </div>
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Fine-tuning progress"
      >
        <div
          className="h-full rounded-full bg-accent transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

function formatStage(stage: FineTuneStage): string {
  const labels: Record<string, string> = {
    generating_data: 'Generating Training Data',
    mining_negatives: 'Mining Hard Negatives',
    training: 'Contrastive Fine-Tuning',
    evaluating: 'Evaluating Checkpoint',
    deploying: 'Deploying Checkpoint',
  }
  return labels[stage] ?? stage
}
