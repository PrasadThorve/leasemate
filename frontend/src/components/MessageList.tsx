import { useEffect, useRef } from 'react'
import type { ChatMessage } from '../types'
import { MessageBubble } from './MessageBubble'

interface MessageListProps {
  messages: ChatMessage[]
  isSending: boolean
}

export function MessageList({ messages, isSending }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  // Keep the newest message in view.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, isSending])

  return (
    // aria-live lets screen readers announce new replies.
    <div className="message-list" aria-live="polite">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}

      {isSending && (
        <div className="message-row from-agent">
          <div className="bubble bubble-agent" aria-label="LeaseMate is typing">
            <span className="bubble-label">LeaseMate</span>
            <span className="typing">
              <span />
              <span />
              <span />
            </span>
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  )
}