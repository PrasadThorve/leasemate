import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Fonts are bundled with the app (no internet needed at demo time).
import '@fontsource-variable/inter'
import '@fontsource-variable/bricolage-grotesque'
import './index.css'
import App from './App.tsx'
import { AdminGate } from './components/AdminLogin.tsx'

// Two pages, no router library needed: /admin is the leasing office dashboard,
// every other address is the chat.
const isAdminPage = window.location.pathname.startsWith('/admin')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {isAdminPage ? <AdminGate /> : <App />}
  </StrictMode>,
)