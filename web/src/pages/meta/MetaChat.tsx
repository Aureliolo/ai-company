import { useCallback, useRef, useState } from 'react'

import { MessageCircle, Send } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { InputField } from '@/components/ui/input-field'
import { LiveRegion } from '@/components/ui/live-region'
import { createLogger } from '@/lib/logger'
import { cn } from '@/lib/utils'
import { useMetaStore } from '@/stores/meta'

const log = createLogger('meta-chat')

interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  confidence?: number
}

// ── Extracted sub-component ─────────────────────────────────────

interface ChatInputAreaProps {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  disabled: boolean
  className?: string
}

function ChatInputArea({
  value,
  onChange,
  onSend,
  disabled,
  className,
}: ChatInputAreaProps) {
  return (
    <div className={cn('flex gap-2', className)}>
      <div className="flex-1">
        <InputField
          label="Chat message"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Ask about signals, proposals..."
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              onSend()
            }
          }}
        />
      </div>
      <Button
        size="sm"
        onClick={onSend}
        disabled={!value.trim() || disabled}
        aria-label="Send message"
      >
        <Send className="h-4 w-4" />
      </Button>
    </div>
  )
}

// ── Message bubble ──────────────────────────────────────────────

function MessageBubble({ msg }: { msg: ChatMessage }) {
  return (
    <div
      className={cn(
        'rounded-md p-card text-sm text-foreground',
        msg.role === 'user' ? 'ml-8 bg-accent/10' : 'mr-8 bg-card',
      )}
    >
      <p className="whitespace-pre-wrap">{msg.content}</p>
      {msg.sources && msg.sources.length > 0 && (
        <p className="mt-1 text-xs text-muted-foreground">
          Sources: {msg.sources.join(', ')}
        </p>
      )}
    </div>
  )
}

// ── Main component ──────────────────────────────────────────────

export function MetaChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const chatLoading = useMetaStore((s) => s.chatLoading)
  const sendChat = useMetaStore((s) => s.sendChat)
  const scrollRef = useRef<HTMLDivElement>(null)
  const msgIdRef = useRef(0)

  const nextMsgId = useCallback(() => ++msgIdRef.current, [])

  const handleSend = useCallback(async () => {
    const question = input.trim()
    if (!question || chatLoading) return

    setInput('')
    setMessages((prev) => [
      ...prev,
      { id: nextMsgId(), role: 'user', content: question },
    ])

    try {
      const response = await sendChat(question)
      setMessages((prev) => [
        ...prev,
        {
          id: nextMsgId(),
          role: 'assistant',
          content: response.answer,
          sources: response.sources,
          confidence: response.confidence,
        },
      ])
    } catch (err) {
      log.error(
        'Chat send failed',
        err instanceof Error ? err.message : String(err),
      )
      setMessages((prev) => [
        ...prev,
        {
          id: nextMsgId(),
          role: 'assistant',
          content: 'Failed to get a response. Please try again.',
        },
      ])
    }

    // Scroll to bottom after render.
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: 'smooth',
      })
    })
  }, [input, chatLoading, sendChat, nextMsgId])

  const triggerSend = useCallback(
    () => void handleSend(),
    [handleSend],
  )

  if (messages.length === 0 && !chatLoading) {
    return (
      <div className="space-y-section-gap">
        <EmptyState
          icon={MessageCircle}
          title="Ask the Chief of Staff"
          description="Ask questions about signals, proposals, or the improvement pipeline."
        />
        <ChatInputArea
          value={input}
          onChange={setInput}
          onSend={triggerSend}
          disabled={chatLoading}
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div
        ref={scrollRef}
        className="max-h-80 space-y-3 overflow-y-auto rounded-md border border-border p-card"
      >
        <LiveRegion politeness="polite">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} msg={msg} />
          ))}
          {chatLoading && (
            <div className="mr-8 animate-pulse rounded-md bg-card p-card text-sm text-muted-foreground">
              Thinking...
            </div>
          )}
        </LiveRegion>
      </div>

      <ChatInputArea
        value={input}
        onChange={setInput}
        onSend={triggerSend}
        disabled={chatLoading}
      />
    </div>
  )
}
