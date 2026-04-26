function fmt(p) {
  return '₹' + (p / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })
}

const STATUS_STYLES = {
  pending:    'bg-slate-100 text-slate-700',
  processing: 'bg-blue-100 text-blue-700',
  completed:  'bg-green-100 text-green-700',
  failed:     'bg-red-100 text-red-700',
}

function ts(d) {
  if (!d) return '—'
  return new Date(d).toLocaleString()
}

export default function PayoutTable({ payouts }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200">
      <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
        <h2 className="font-semibold text-slate-900">Payouts</h2>
        <span className="text-xs text-slate-500">Auto-refreshes every 2s</span>
      </div>
      {payouts.length === 0 ? (
        <div className="px-5 py-8 text-center text-sm text-slate-500">
          No payouts yet.
        </div>
      ) : (
        <table className="w-full text-sm">
          <thead className="text-xs text-slate-500 uppercase">
            <tr>
              <th className="text-left px-5 py-2">Created</th>
              <th className="text-left px-5 py-2">Amount</th>
              <th className="text-left px-5 py-2">Status</th>
              <th className="text-left px-5 py-2">Attempts</th>
              <th className="text-left px-5 py-2">Failure reason</th>
            </tr>
          </thead>
          <tbody>
            {payouts.map(p => (
              <tr key={p.id} className="border-t border-slate-100">
                <td className="px-5 py-2 text-slate-600">{ts(p.created_at)}</td>
                <td className="px-5 py-2 font-medium">{fmt(p.amount_paise)}</td>
                <td className="px-5 py-2">
                  <span className={`px-2 py-0.5 rounded text-xs ${STATUS_STYLES[p.status]}`}>
                    {p.status}
                  </span>
                </td>
                <td className="px-5 py-2 text-slate-600">{p.attempt_count}</td>
                <td className="px-5 py-2 text-slate-500 text-xs">{p.failure_reason || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
