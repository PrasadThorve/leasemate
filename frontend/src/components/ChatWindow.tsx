import { COMPANIES, SUGGESTIONS } from '../config'
import { useChat } from '../hooks/useChat'
import type { Company } from '../types'
import { Composer } from './Composer'
import { Header } from './Header'
import { MessageList } from './MessageList'
import { Welcome } from './Welcome'

interface ChatWindowProps {
  company: Company
  onCompanyChange: (widgetKey: string) => void
}

/** Puts the pieces together. All the state comes from the useChat hook. */
export function ChatWindow({ company, onCompanyChange }: ChatWindowProps) {
  const { messages, isSending, error, send, startNewChat } = useChat(company.widgetKey)
  const isEmpty = messages.length === 0 && !isSending

  return (
    <div className="app">
      <Header
        companies={COMPANIES}
        company={company}
        onCompanyChange={onCompanyChange}
        onNewChat={startNewChat}
        canStartNewChat={messages.length > 0 && !isSending}
      />

      <main className="stage">
        <section className="chat-card" aria-label="Chat with LeaseMate">
          {/* Card header: who you're talking to, and a live status badge. */}
          <div className="card-header">
            <span className="agent-avatar" aria-hidden="true">
              LM
            </span>
            <div className="agent-meta">
              <span className="agent-name">LeaseMate agent</span>
              <span className="agent-sub">
                {company.name} · {company.areas}
              </span>
            </div>
            <span className="live-badge">
              <span className="live-dot" aria-hidden="true" />
              Live
            </span>
          </div>

          <div className="card-body">
            {isEmpty ? (
              <Welcome companyName={company.name} suggestions={SUGGESTIONS} onPick={send} disabled={isSending} />
            ) : (
              <MessageList messages={messages} isSending={isSending} />
            )}
          </div>

          <div className="card-footer">
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
            <Composer onSend={send} disabled={isSending} />
          </div>
        </section>

        <p className="disclaimer">AI assistant. Rent and availability come live from the leasing system.</p>
      </main>
    </div>
  )
}