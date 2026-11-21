export type Role = 'user' | 'assistant'

/** One message as the UI shows it. */
export interface ChatMessage {
  id: string
  role: Role
  content: string
  toolsUsed?: string[]
  guardrail?: Guardrail | null
}

/** POST /chat response. */
export interface ChatResponse {
  thread_id: string
  reply: string
  tools_used: string[]
  guardrail: Guardrail | null
}

/** GET /chat/{thread_id} response. */
export interface HistoryResponse {
  thread_id: string
  messages: { role: Role; content: string }[]
}

/** A rental company whose chat widget we can show. */
export interface Company {
  name: string
  widgetKey: string
  areas: string
}

/** Which guardrail acted on a turn (matches the backend's guardrail field). */
export type Guardrail = 'handoff' | 'fair_housing' | 'prompt_injection'