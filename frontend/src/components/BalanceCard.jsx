function fmt(paise) {
  if (paise == null) return '—'
  return '₹' + (paise / 100).toLocaleString('en-IN', {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  })
}

export default function BalanceCard({ balance }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <div className="text-xs uppercase tracking-wider text-slate-500">Available</div>
        <div className="text-2xl font-semibold text-slate-900 mt-1">
          {fmt(balance?.available_paise)}
        </div>
        <div className="text-xs text-slate-400 mt-1">Can be withdrawn</div>
      </div>
      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <div className="text-xs uppercase tracking-wider text-slate-500">Held</div>
        <div className="text-2xl font-semibold text-amber-600 mt-1">
          {fmt(balance?.held_paise)}
        </div>
        <div className="text-xs text-slate-400 mt-1">In flight payouts</div>
      </div>
      <div className="bg-white rounded-lg border border-slate-200 p-5">
        <div className="text-xs uppercase tracking-wider text-slate-500">Total</div>
        <div className="text-2xl font-semibold text-slate-700 mt-1">
          {fmt(balance?.total_paise)}
        </div>
        <div className="text-xs text-slate-400 mt-1">Available + held</div>
      </div>
    </div>
  )
}
