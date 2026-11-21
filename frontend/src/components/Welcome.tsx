interface WelcomeProps {
  companyName: string
  suggestions: string[]
  onPick: (text: string) => void
  disabled: boolean
}

/** Shown before the first message: a headline plus one-click starter questions. */
export function Welcome({ companyName, suggestions, onPick, disabled }: WelcomeProps) {
  return (
    <section className="welcome">
      <p className="eyebrow">Leasing AI · Pune</p>
      <h1 className="display">Find your next home in Pune.</h1>
      <p className="lead">
        I'm the leasing assistant for {companyName}. Ask about flats, rent, pets or parking, or book a site visit,
        any time of day.
      </p>
      <div className="suggestions">
        {suggestions.map((text) => (
          <button key={text} type="button" className="chip" onClick={() => onPick(text)} disabled={disabled}>
            <span className="chip-dot" aria-hidden="true" />
            {text}
          </button>
        ))}
      </div>
    </section>
  )
}