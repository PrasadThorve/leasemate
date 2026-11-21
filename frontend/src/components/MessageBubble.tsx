import { Fragment } from 'react'
import { TOOL_LABELS } from '../config'
import type { ChatMessage } from '../types'

/** Renders **bold** text inside one line. */
function InlineText({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return (
    <>
      {parts.map((part, i) =>
        part.startsWith('**') && part.endsWith('**') ? (
          <strong key={i}>{part.slice(2, -2)}</strong>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  )
}

/**
 * A tiny formatter for the agent's replies: paragraphs, "- " bullet lists and **bold**.
 * It builds React elements (never raw HTML), so a reply can't inject markup into the page.
 */
function FormattedText({ text }: { text: string }) {
  const blocks: { type: 'p' | 'ul'; lines: string[] }[] = []
  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim()
    if (!line) continue
    const bullet = line.match(/^[-*•]\s+(.*)$/)
    const last = blocks[blocks.length - 1]
    if (bullet) {
      if (last?.type === 'ul') last.lines.push(bullet[1])
      else blocks.push({ type: 'ul', lines: [bullet[1]] })
    } else {
      blocks.push({ type: 'p', lines: [line] })
    }
  }

  return (
    <>
      {blocks.map((block, i) =>
        block.type === 'ul' ? (
          <ul key={i}>
            {block.lines.map((line, j) => (
              <li key={j}>
                <InlineText text={line} />
              </li>
            ))}
          </ul>
        ) : (
          <p key={i}>
            <InlineText text={block.lines[0]} />
          </p>
        ),
      )}
    </>
  )
}

function CheckIcon() {
  return (
    <svg className="check-icon" viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="8" cy="8" r="8" />
      <path d="M4.5 8.2l2.2 2.2 4.8-4.8" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  const tools = [...new Set(message.toolsUsed ?? [])]

  return (
    <div className={`message-row ${isUser ? 'from-user' : 'from-agent'}`}>
      <div className="message-body">
        <div className={`bubble ${isUser ? 'bubble-user' : 'bubble-agent'}`}>
          <span className="bubble-label">{isUser ? 'You' : 'LeaseMate'}</span>
          {isUser ? <p>{message.content}</p> : <FormattedText text={message.content} />}
        </div>

        {/* An activity log of the tools the agent used, so you can see it checked real data. */}
        {tools.length > 0 && (
          <ul className="activity" aria-label="What the assistant did">
            {tools.map((tool) => (
              <li key={tool}>
                <CheckIcon />
                {TOOL_LABELS[tool] ?? tool}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}