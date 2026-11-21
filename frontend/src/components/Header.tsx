import type { Company } from "../types"

interface HeaderProps {
  companies: Company[]
  company: Company
  onCompanyChange: (widgetKey: string) => void
  onNewChat: () => void
  canStartNewChat: boolean
}

/** The white top bar: LeaseMate brand on the left, company picker and New chat on the right. */
export function Header({ companies, company, onCompanyChange, onNewChat, canStartNewChat }: HeaderProps) {
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">
          LM
        </span>
        <span className="brand-name">LeaseMate</span>
      </div>

      <div className="topbar-actions">
        {/* Switching company shows tenant isolation: each company only sees its own homes. */}
        <label className="company-picker">
          <span className="visually-hidden">Company</span>
          <select value={company.widgetKey} onChange={(e) => onCompanyChange(e.target.value)}>
            {companies.map((c) => (
              <option key={c.widgetKey} value={c.widgetKey}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="button-primary" onClick={onNewChat} disabled={!canStartNewChat}>
          New chat
        </button>
      </div>
    </header>
  )
}