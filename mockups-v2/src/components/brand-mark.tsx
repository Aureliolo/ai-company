interface BrandMarkProps {
  size?: "sm" | "md" | "lg"
}

export function BrandMark({ size = "md" }: BrandMarkProps) {

  const sizes = {
    sm: { text: "text-xs", tracking: "tracking-wider" },
    md: { text: "text-sm", tracking: "tracking-wider" },
    lg: { text: "text-lg", tracking: "tracking-widest" },
  }

  const s = sizes[size]

  return (
    <span
      className={`font-mono font-semibold ${s.text} ${s.tracking} text-accent/70`}
    >
      SynthOrg
    </span>
  )
}
