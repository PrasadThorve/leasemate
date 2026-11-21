import { useEffect, useState } from 'react'
import { ApiError, fetchActivity } from '../api'
import { COMPANIES, HANDOFF_REASONS, STATUS_LABELS } from '../config'
import type { ActivityResponse } from '../types'

/** Leasing office dashboard (/admin): what the AI agent did. Read-only, one company at a time. */
export function AdminPage() {
  const [adminKey, setAdminKey] = useState(COMPANIES[0].adminKey)
  const company = COMPANIES.find((c) => c.adminKey === adminKey) ?? COMPANIES[0]

  const [data, setData] = useState<ActivityResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [refreshCount, setRefreshCount] = useState(0) // bump it to load again

  useEffect(() => {
    let ignore = false // a newer request (other company, refresh) replaces this one

    fetchActivity(adminKey)
      .then((result) => {
        if (ignore) return
        setData(result)
        setError(null)
      })
      .catch((err) => {
        if (!ignore) setError(err instanceof ApiError ? err.message : 'Something went wrong.')
      })
      .finally(() => {
        if (!ignore) setIsLoading(false)
      })

    return () => {
      ignore = true
    }
  }, [adminKey, refreshCount])

  function changeCompany(key: string) {
    setAdminKey(key)
    setData(null) // never show one company's data under another company's name
    setError(null)
    setIsLoading(true)
  }

  function refresh() {
    setIsLoading(true)
    setRefreshCount((n) => n + 1)
  }

  const scheduledVisits = data?.tours.filter((t) => t.status === 'scheduled').length
  const openHandoffs = data?.handoffs.filter((h) => h.status === 'open').length

  return (
    <div className="admin-page">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            LM
          </span>
          <span className="brand-name">LeaseMate</span>
          <span className="brand-tag">Leasing office</span>
        </div>

        <div className="topbar-actions">
          <label className="company-picker">
            <span className="visually-hidden">Company</span>
            <select value={adminKey} onChange={(e) => changeCompany(e.target.value)}>
              {COMPANIES.map((c) => (
                <option key={c.adminKey} value={c.adminKey}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="button-primary" onClick={refresh} disabled={isLoading}>
            {isLoading ? 'Loading…' : 'Refresh'}
          </button>
        </div>
      </header>

      <main className="admin-main">
        <p className="eyebrow">Leasing office</p>
        <h1 className="admin-title">What the AI agent did for {company.name}</h1>
        <p className="lead">
          Guest cards, site visits and handoffs created in chat, newest first. <a href="/">Open the chat</a>
        </p>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <div className="stats">
          <Stat value={data?.leads.length} label="Guest cards" />
          <Stat value={scheduledVisits} label="Site visits scheduled" />
          <Stat value={openHandoffs} label="Open handoffs" />
        </div>

        <section className="admin-section" aria-label="Guest cards">
          <h2>Guest cards</h2>
          <div className="table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Contact</th>
                  <th>Property</th>
                  <th>Wants</th>
                  <th>Budget</th>
                  <th>Move-in</th>
                  <th>Pets</th>
                  <th>Status</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {data?.leads.map((lead) => (
                  <tr key={lead.id}>
                    <td className="strong">{lead.name}</td>
                    <td>
                      <span className="nowrap">{lead.phone ?? '—'}</span>
                      {lead.email && <span className="muted">{lead.email}</span>}
                    </td>
                    <td>{lead.property_name}</td>
                    <td className="nowrap">{lead.wants ?? '—'}</td>
                    <td className="nowrap">{lead.budget ?? '—'}</td>
                    <td className="nowrap">{lead.move_in ?? '—'}</td>
                    <td>{lead.pets ?? '—'}</td>
                    <td>
                      <Badge status={lead.status} />
                    </td>
                    <td className="time">{lead.created_at}</td>
                  </tr>
                ))}
                <EmptyRow show={data?.leads.length === 0} columns={9} text="No guest cards yet." />
              </tbody>
            </table>
          </div>
        </section>

        <section className="admin-section" aria-label="Site visits">
          <h2>Site visits</h2>
          <div className="table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Visit (IST)</th>
                  <th>Property</th>
                  <th>Visitor</th>
                  <th>Phone</th>
                  <th>Status</th>
                  <th>Booked</th>
                </tr>
              </thead>
              <tbody>
                {data?.tours.map((tour) => (
                  <tr key={tour.id}>
                    <td className="nowrap strong">{tour.visit_time}</td>
                    <td>{tour.property_name}</td>
                    <td>{tour.visitor}</td>
                    <td className="nowrap">{tour.phone ?? '—'}</td>
                    <td>
                      <Badge status={tour.status} />
                    </td>
                    <td className="time">{tour.booked_at}</td>
                  </tr>
                ))}
                <EmptyRow show={data?.tours.length === 0} columns={6} text="No site visits booked yet." />
              </tbody>
            </table>
          </div>
        </section>

        <section className="admin-section" aria-label="Handoffs">
          <h2>Handoffs to the leasing team</h2>
          <div className="table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Reason</th>
                  <th>What the agent wrote</th>
                  <th>Property</th>
                  <th>Guest</th>
                  <th>Status</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {data?.handoffs.map((handoff) => (
                  <tr key={handoff.id}>
                    <td className="nowrap strong">{HANDOFF_REASONS[handoff.reason] ?? handoff.reason}</td>
                    <td className="summary">{handoff.summary}</td>
                    <td>{handoff.property_name ?? '—'}</td>
                    <td>{handoff.lead_name ?? '—'}</td>
                    <td>
                      <Badge status={handoff.status} />
                    </td>
                    <td className="time">{handoff.created_at}</td>
                  </tr>
                ))}
                <EmptyRow show={data?.handoffs.length === 0} columns={6} text="No handoffs yet." />
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  )
}

function Stat({ value, label }: { value: number | undefined; label: string }) {
  return (
    <div className="stat">
      <span className="stat-value">{value ?? '–'}</span>
      <span className="stat-label">{label}</span>
    </div>
  )
}

function Badge({ status }: { status: string }) {
  return <span className={`badge badge-${status}`}>{STATUS_LABELS[status] ?? status}</span>
}

function EmptyRow({ show, columns, text }: { show: boolean; columns: number; text: string }) {
  if (!show) return null
  return (
    <tr>
      <td colSpan={columns} className="empty">
        {text} Chat with the agent and it will show up here.
      </td>
    </tr>
  )
}