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
  adminKey: string
  areas: string
}


/** GET /admin/activity response. Mirrors backend/app/admin.py. */
export interface LeadRow {
  id: number
  name: string
  phone: string | null
  email: string | null
  property_name: string
  wants: string | null
  budget: string | null
  move_in: string | null
  pets: string | null
  status: string
  created_at: string
}

export interface TourRow {
  id: number
  visit_time: string
  property_name: string
  visitor: string
  phone: string | null
  status: string
  booked_at: string
}

export interface HandoffRow {
  id: number
  reason: string
  summary: string
  property_name: string | null
  lead_name: string | null
  status: string
  created_at: string
}

export interface ActivityResponse {
  company_name: string
  leads: LeadRow[]
  tours: TourRow[]
  handoffs: HandoffRow[]
}

/** Which guardrail acted on a turn (matches the backend's guardrail field). */
export type Guardrail = 'handoff' | 'fair_housing' | 'prompt_injection'