import type { Company, Guardrail } from './types'

// Set VITE_API_URL in frontend/.env to point at a different backend.
export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'


export const COMPANIES: Company[] = [
  {
    name: 'Sahyadri Rental Communities',
    widgetKey: 'sahyadri-demo-key',
    adminKey: 'sahyadri-admin-demo',
    areas: 'Hinjewadi · Kharadi · Baner',
  },
  {
    name: 'Indrayani Homes',
    widgetKey: 'indrayani-demo-key',
    adminKey: 'indrayani-admin-demo',
    areas: 'Koregaon Park',
  },
]

export const SUGGESTIONS = [
  'Show me your properties',
  '2 BHK in Hinjewadi under ₹28,000',
  'Do you allow pets?',
  'Book a site visit this weekend',
]

// Friendly labels for the tools the agent used, shown under its replies.
export const TOOL_LABELS: Record<string, string> = {
  list_properties: 'Looked up properties',
  get_property_details: 'Read property details',
  check_availability: 'Checked live availability',
  create_guest_card: 'Saved your details',
  get_tour_slots: 'Checked visit times',
  book_tour: 'Booked a site visit',
  request_human_handoff: 'Handed over to the leasing team',
}

// Shown under a reply when a guardrail acted on that message.
export const GUARDRAIL_LABELS: Record<Guardrail, string> = {
  fair_housing: 'Fair housing guardrail applied',
  prompt_injection: 'Unsafe request blocked',
  handoff: 'Flagged for the leasing team',
}


// Dashboard labels for the database's status and reason codes.
export const STATUS_LABELS: Record<string, string> = {
  new: 'New',
  tour_scheduled: 'Visit booked',
  scheduled: 'Scheduled',
  cancelled: 'Cancelled',
  open: 'Open',
  resolved: 'Resolved',
}

export const HANDOFF_REASONS: Record<string, string> = {
  negotiation: 'Negotiation',
  complaint: 'Complaint',
  resident_issue: 'Resident issue',
  human_requested: 'Wants a person',
  other: 'Other',
}