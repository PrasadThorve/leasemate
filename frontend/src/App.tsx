import { useState } from 'react'
import { ChatWindow } from './components/ChatWindow'
import { COMPANIES } from './config'

function App() {
  const [widgetKey, setWidgetKey] = useState(COMPANIES[0].widgetKey)
  const company = COMPANIES.find((c) => c.widgetKey === widgetKey) ?? COMPANIES[0]

  // key={widgetKey}: when the company changes, React throws the old chat away and
  // mounts a fresh one, so no messages can leak from one company's chat to another.
  return <ChatWindow key={widgetKey} company={company} onCompanyChange={setWidgetKey} />
}

export default App