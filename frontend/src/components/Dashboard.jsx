import { useEffect, useState, useCallback } from 'react'
import { api } from '../api'
import BalanceCard from './BalanceCard'
import PayoutForm from './PayoutForm'
import PayoutTable from './PayoutTable'
import TransactionList from './TransactionList'

export default function Dashboard({ merchantId }) {
  const [balance, setBalance] = useState(null)
  const [payouts, setPayouts] = useState([])
  const [ledger, setLedger] = useState([])
  const [bankAccounts, setBankAccounts] = useState([])

  const refresh = useCallback(async () => {
    const [b, p, l, ba] = await Promise.all([
      api.getBalance(merchantId),
      api.getPayouts(merchantId),
      api.getLedger(merchantId),
      api.getBankAccounts(merchantId),
    ])
    setBalance(b); setPayouts(p); setLedger(l); setBankAccounts(ba)
  }, [merchantId])

  useEffect(() => { refresh() }, [refresh])

  // Poll every 2 seconds — payouts move through states in the background
  useEffect(() => {
    const id = setInterval(refresh, 2000)
    return () => clearInterval(id)
  }, [refresh])

  return (
    <div className="space-y-6">
      <BalanceCard balance={balance} />
      <div className="grid md:grid-cols-2 gap-6">
        <PayoutForm
          merchantId={merchantId}
          bankAccounts={bankAccounts}
          onSubmitted={refresh}
        />
        <TransactionList ledger={ledger} />
      </div>
      <PayoutTable payouts={payouts} />
    </div>
  )
}
