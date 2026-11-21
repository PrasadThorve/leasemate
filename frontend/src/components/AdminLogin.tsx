import { useState, type FormEvent } from 'react'
import { ADMIN_LOGIN } from '../config'
import { AdminPage } from './AdminPage'

// Remembers the sign-in until this browser tab is closed.
const SESSION_KEY = 'leasemate-admin-signed-in'

/** The /admin page: the sign-in form first, the dashboard after a correct login. */
export function AdminGate() {
  const [isSignedIn, setIsSignedIn] = useState(readSignedIn)

  function signIn() {
    saveSignedIn(true)
    setIsSignedIn(true)
  }

  function signOut() {
    saveSignedIn(false)
    setIsSignedIn(false)
  }

  return isSignedIn ? <AdminPage onSignOut={signOut} /> : <AdminLogin onSignIn={signIn} />
}

function AdminLogin({ onSignIn }: { onSignIn: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault() // stay on the page instead of reloading it
    if (username.trim() === ADMIN_LOGIN.username && password === ADMIN_LOGIN.password) {
      onSignIn()
    } else {
      setError('Wrong username or password.')
      setPassword('')
    }
  }

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
      </header>

      <main className="login-main">
        <form className="login-card" onSubmit={handleSubmit}>
          <p className="eyebrow">Leasing office</p>
          <h1>Sign in</h1>

          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}

          <label className="field">
            Username
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              required
            />
          </label>

          <label className="field">
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>

          <button type="submit" className="button-primary">
            Sign in
          </button>
          <a className="login-back" href="/">
            Back to the chat
          </a>
        </form>
      </main>
    </div>
  )
}

// sessionStorage can be blocked (some privacy settings); then the user just signs in again.
function readSignedIn(): boolean {
  try {
    return sessionStorage.getItem(SESSION_KEY) === 'yes'
  } catch {
    return false
  }
}

function saveSignedIn(signedIn: boolean) {
  try {
    if (signedIn) sessionStorage.setItem(SESSION_KEY, 'yes')
    else sessionStorage.removeItem(SESSION_KEY)
  } catch {
    // ignore: sign-in still works for this page view
  }
}