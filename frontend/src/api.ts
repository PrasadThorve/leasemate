// Every call to the backend goes through this file.

import { API_URL } from './config'
import type { ActivityResponse, ChatResponse, HistoryResponse } from './types'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, headers: Record<string, string>, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...headers },
    })
  } catch {
    // fetch only throws when it can't reach the server at all.
    throw new ApiError(0, "Can't reach the LeaseMate API. Is the backend running on port 8000?")
  }

  if (!response.ok) {
    // FastAPI puts error messages in {"detail": "..."}.
    const body = await response.json().catch(() => null)
    const detail = typeof body?.detail === 'string' ? body.detail : `Request failed (${response.status}).`
    throw new ApiError(response.status, detail)
  }
  return (await response.json()) as T
}

export function sendMessage(widgetKey: string, message: string, threadId: string | null) {
  return request<ChatResponse>('/chat', { 'X-Widget-Key': widgetKey }, {
    method: 'POST',
    body: JSON.stringify({ message, thread_id: threadId }),
  })
}

export function fetchHistory(widgetKey: string, threadId: string) {
  return request<HistoryResponse>(`/chat/${encodeURIComponent(threadId)}`, { 'X-Widget-Key': widgetKey })
}

/** Leasing office dashboard: everything the agent did for one company. */
export function fetchActivity(adminKey: string) {
  return request<ActivityResponse>('/admin/activity', { 'X-Admin-Key': adminKey })
}