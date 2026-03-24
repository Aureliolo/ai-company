import { getInitials } from "@/lib/utils.ts"

interface AgentAvatarProps {
  name: string
  size?: number
}

export function AgentAvatar({ name, size = 40 }: AgentAvatarProps) {
  const initials = getInitials(name)

  return (
    <div
      className="rounded-full bg-accent/10 border-2 border-accent/30 flex items-center justify-center font-bold text-accent font-mono shrink-0"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.32,
      }}
    >
      {initials}
    </div>
  )
}
