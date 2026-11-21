import { useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'

interface ComposerProps {
  onSend: (text: string) => void
  disabled: boolean
}

/** The message box. Enter sends; Shift+Enter adds a new line. */
export function Composer({ onSend, disabled }: ComposerProps) {
  const [text, setText] = useState('')

  function submit() {
    if (!text.trim() || disabled) return
    onSend(text)
    setText('')
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    submit()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <label htmlFor="message" className="visually-hidden">
        Message
      </label>
      <textarea
        id="message"
        rows={1}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask about flats, rent or site visits…"
        maxLength={2000}
        autoFocus
      />
      <button type="submit" className="send-button" aria-label="Send" disabled={disabled || !text.trim()}>
        <svg viewBox="0 0 20 20" aria-hidden="true">
          <path d="M4 10h11M10.5 5l5 5-5 5" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
    </form>
  )
}