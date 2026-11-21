// All the chat logic lives in this hook; components only display what it returns.

import { useCallback, useEffect, useState } from 'react'
import { fetchHistory, sendMessage } from '../api'
import type { ChatMessage } from '../types'

// The thread id is saved per company, so a page refresh continues the same chat.
const storageKey = (widgetKey: string) => `leasemate:thread:${widgetKey}`

function loadThreadId(widgetKey: string): string | null {
  try {
    return localStorage.getItem(storageKey(widgetKey))
  } catch {
    return null // storage can be blocked, e.g. in some private browsing modes
  }
}

function saveThreadId(widgetKey: string, threadId: string | null) {
  try {
    if (threadId) localStorage.setItem(storageKey(widgetKey), threadId)
    else localStorage.removeItem(storageKey(widgetKey))
  } catch {
    // ignore: the chat still works, it just won't survive a refresh
  }
}

export function useChat(widgetKey: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [threadId, setThreadId] = useState<string | null>(() => loadThreadId(widgetKey))
  // The thread we started with. It never changes, so the restore effect runs only once.
  const [initialThreadId] = useState(threadId)
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // On first load, restore the saved conversation from the backend.
  useEffect(() => {
    if (!initialThreadId) return
    let ignore = false // set if the component unmounts before the request finishes

    fetchHistory(widgetKey, initialThreadId)
      .then((history) => {
        if (ignore) return
        if (history.messages.length === 0) {
          // The backend forgot this chat (its memory resets on restart): start fresh.
          saveThreadId(widgetKey, null)
          setThreadId(null)
          return
        }
        setMessages(history.messages.map((m) => ({ id: crypto.randomUUID(), ...m })))
      })
      .catch(() => {
        // Restoring is a nice-to-have; if it fails, just start with an empty chat.
      })

    return () => {
      ignore = true
    }
  }, [widgetKey, initialThreadId])

  const send = useCallback(
    async (text: string) => {
      const message = text.trim()
      if (!message || isSending) return

      setError(null)
      setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: 'user', content: message }])
      setIsSending(true)

      try {
        const response = await sendMessage(widgetKey, message, threadId)
        setThreadId(response.thread_id)
        saveThreadId(widgetKey, response.thread_id)
        setMessages((prev) => [
          ...prev,
          { id: crypto.randomUUID(), role: 'assistant', content: response.reply, toolsUsed: response.tools_used },
        ])
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
      } finally {
        setIsSending(false)
      }
    },
    [widgetKey, threadId, isSending],
  )

  const startNewChat = useCallback(() => {
    saveThreadId(widgetKey, null)
    setThreadId(null)
    setMessages([])
    setError(null)
  }, [widgetKey])

  return { messages, isSending, error, send, startNewChat }
}