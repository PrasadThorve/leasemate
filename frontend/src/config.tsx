import type { Company } from './types'

// Set VITE_API_URL in frontend/.env to point at a different backend.
export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

// Widget keys are public: they say which company's chat this is, like a site id.
// The backend (app/config.py) maps each key to a company.
export const COMPANIES: Company[] = [
  { name: 'Sahyadri Rental Communities', widgetKey: 'sahyadri-demo-key', areas: 'Hinjewadi · Kharadi · Baner' },
  { name: 'Indrayani Homes', widgetKey: 'indrayani-demo-key', areas: 'Koregaon Park' },
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
}