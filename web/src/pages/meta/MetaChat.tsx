import { useCallback, useRef, useState } from 'react'

import { MessageCircle, Send } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { InputField } from '@/components/ui/input-field'
import { useMetaStore } from '@/stores/meta'

let _msgId = 0

interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  confidence?: number
}

export function MetaChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const chatLoading = useMetaStore((s) => s.chatLoading)
  const sendChat = useMetaStore((s) => s.sendChat)
  const scrollRef = useRef<HTMLDivElement>(null)

  const handleSend = useCallback(async () => {
    const question = input.trim()
    if (!question || chatLoading) return

    setInput('')
    setMessages((prev) => [
      ...prev,
      { id: ++_msgId, role: 'user', content: question },
    ])

    try {
      const response = await sendChat(question)
      setMessages((prev) => [
        ...prev,
        {
          id: ++_msgId,
          role: 'assistant',
          content: response.answer,
          sources: response.sources,
          confidence: response.confidence,
        },
      ])
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: ++_msgId,
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
  }, [input, chatLoading, sendChat])

  if (messages.length === 0 && !chatLoading) {
    return (
      <div className="space-y-4">
        <EmptyState
          icon={MessageCircle}
          title="Ask the Chief of Staff"
          description="Ask questions about signals, proposals, or the improvement pipeline."
        />
        <div className="flex gap-2">
          <div className="flex-1">
            <InputField
              label=""
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about signals, proposals..."
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  void handleSend()
                }
              }}
            />
          </div>
          <Button
            size="sm"
            onClick={() => void handleSend()}
            disabled={!input.trim() || chatLoading}
            className="mt-6"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div
        ref={scrollRef}
        className="max-h-80 space-y-3 overflow-y-auto rounded-md border border-border p-3"
      >
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`rounded-md p-3 text-sm ${
              msg.role === 'user'
                ? 'ml-8 bg-accent/10 text-foreground'
                : 'mr-8 bg-card text-foreground'
            }`}
          >
            <p className="whitespace-pre-wrap">{msg.content}</p>
            {msg.sources && msg.sources.length > 0 && (
              <p className="mt-1 text-xs text-muted-foreground">
                Sources: {msg.sources.join(', ')}
              </p>
            )}
          </div>
        ))}
        {chatLoading && (
          <div className="mr-8 animate-pulse rounded-md bg-card p-3 text-sm text-muted-foreground">
            Thinking...
          </div>
        )}
      </div>

      <div className="flex gap-2">
        <div className="flex-1">
          <InputField
            label=""
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about signals, proposals..."
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                void handleSend()
              }
            }}
          />
        </div>
        <Button
          size="sm"
          onClick={() => void handleSend()}
          disabled={!input.trim() || chatLoading}
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
