import { useState } from 'react'
import { api, uuid } from '../api'

export default function PayoutForm({ merchantId, bankAccounts, onSubmitted }) {
  const [amount, setAmount] = useState('')
  const [bankId, setBankId] = useState('')
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState(null)

  async function submit() {
    setFeedback(null)
    const effectiveBankId = bankId || bankAccounts[0]?.id || ''
    if (!amount || !effectiveBankId) {
      setFeedback({ kind: 'err', text: 'Amount and bank account are required.' })
      return
    }
    const amount_paise = Math.round(parseFloat(amount) * 100)
    if (!Number.isFinite(amount_paise) || amount_paise <= 0) {
      setFeedback({ kind: 'err', text: 'Enter a valid amount in rupees.' })
      return
    }

    setBusy(true)
    try {
      const key = uuid()
      await api.requestPayout(
        merchantId,
        { amount_paise, bank_account_id: effectiveBankId },
        key,
      )
      setFeedback({ kind: 'ok', text: 'Payout requested.' })
      setAmount('')
      onSubmitted?.()
    } catch (err) {
      const msg = err?.body?.error || err?.message || 'Request failed.'
      setFeedback({ kind: 'err', text: String(msg) })
    } finally {
      setBusy(false)
    }
  }

  const defaultBank = bankAccounts[0]?.id

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-5">
      <h2 className="font-semibold text-slate-900 mb-4">Request Payout</h2>

      <label className="block text-xs text-slate-600 mb-1">Amount (₹)</label>
      <input
        type="number"
        step="0.01"
        value={amount}
        onChange={e => setAmount(e.target.value)}
        placeholder="e.g. 1500.00"
        className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm mb-3"
      />

      <label className="block text-xs text-slate-600 mb-1">Bank account</label>
      <select
        value={bankId || defaultBank || ''}
        onChange={e => setBankId(e.target.value)}
        className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm mb-4 bg-white"
      >
        <option value="">Select…</option>
        {bankAccounts.map(b => (
          <option key={b.id} value={b.id}>
            {b.account_holder_name} ({b.masked_account}) — {b.ifsc_code}
          </option>
        ))}
      </select>

      <button
        onClick={submit}
        disabled={busy}
        className="bg-slate-900 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-slate-700 disabled:opacity-50"
      >
        {busy ? 'Submitting…' : 'Submit Payout'}
      </button>

      {feedback && (
        <div
          className={`mt-3 text-sm ${
            feedback.kind === 'ok' ? 'text-green-700' : 'text-red-700'
          }`}
        >
          {feedback.text}
        </div>
      )}
    </div>
  )
}
