const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1'

async function request(path, options = {}) {
  const { headers: extraHeaders, ...rest } = options
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(extraHeaders || {}) },
    ...rest,
  })
  const text = await res.text()
  const data = text ? JSON.parse(text) : {}
  if (!res.ok) throw { status: res.status, body: data }
  return data
}

export function uuid() {
  // Lightweight UUIDv4 — fine for an Idempotency-Key header
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

export const api = {
  listMerchants: () => request('/merchants/'),
  getBalance: (id) => request(`/merchants/${id}/balance/`),
  getLedger: (id) => request(`/merchants/${id}/ledger/`),
  getBankAccounts: (id) => request(`/merchants/${id}/bank-accounts/`),
  getPayouts: (id) => request(`/merchants/${id}/payouts/`),
  requestPayout: (id, body, idempotencyKey) =>
    request(`/merchants/${id}/payouts/request/`, {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify(body),
    }),
}
