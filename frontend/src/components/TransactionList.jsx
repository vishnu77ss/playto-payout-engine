function fmt(p) {
  const sign = p < 0 ? '-' : '+'
  return sign + '₹' + (Math.abs(p) / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })
}

const TYPE_STYLES = {
  credit: 'text-green-700',
  debit: 'text-red-700',
  reversal: 'text-amber-700',
}

export default function TransactionList({ ledger }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-5">
      <h2 className="font-semibold text-slate-900 mb-3">Recent ledger entries</h2>
      {ledger.length === 0 ? (
        <div className="text-sm text-slate-500">No entries.</div>
      ) : (
        <ul className="divide-y divide-slate-100">
          {ledger.slice(0, 10).map(e => (
            <li key={e.id} className="py-2 flex items-center justify-between text-sm">
              <div>
                <div className="text-slate-700">{e.description}</div>
                <div className="text-xs text-slate-400">
                  {e.entry_type} · {new Date(e.created_at).toLocaleString()}
                </div>
              </div>
              <div className={`font-medium ${TYPE_STYLES[e.entry_type]}`}>
                {fmt(e.amount_paise)}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
