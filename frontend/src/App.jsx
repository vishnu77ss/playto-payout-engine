import { useEffect, useState } from 'react'
import { api } from './api'
import Dashboard from './components/Dashboard'

export default function App() {
  const [merchants, setMerchants] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.listMerchants()
      .then(list => {
        setMerchants(list)
        if (list.length && !activeId) setActiveId(list[0].id)
      })
      .catch(e => setError(`Could not load merchants. Is the backend running at port 8000?`))
  }, [])

  return (
    <div className="min-h-screen">
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">Playto Payouts</h1>
            <p className="text-xs text-slate-500">Merchant balance & payout dashboard</p>
          </div>
          {merchants.length > 0 && (
            <select
              value={activeId || ''}
              onChange={e => setActiveId(e.target.value)}
              className="border border-slate-300 rounded-md px-3 py-2 text-sm bg-white"
            >
              {merchants.map(m => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
          )}
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-md text-sm">
            {error}
          </div>
        )}
        {activeId && <Dashboard merchantId={activeId} />}
      </main>
    </div>
  )
}
