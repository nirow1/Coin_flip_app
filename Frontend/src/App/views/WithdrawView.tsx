import { useState } from 'react';

export default function WithdrawPage() {
  const [method, setMethod] = useState<'bank' | 'solana'>('bank');
  const [amount, setAmount] = useState('');

  return (
    <div className="p-6 max-w-7xl text-gray-900">
      <h2 className="text-3xl text-[#efbf04] mb-5 font-[Alexandria]">Withdraw</h2>
      <div className="grid grid-cols-2 gap-5 items-start">

        {/* Left: method selector */}
        <div className="flex flex-col gap-3">
          <button
            onClick={() => setMethod('bank')}
            className={`w-full flex items-center gap-4 p-5 rounded-2xl border-2 transition-all text-left ${
              method === 'bank'
                ? 'border-[#efbf04] bg-[#fffdf0] shadow-sm'
                : 'border-gray-100 bg-white hover:border-[#efbf04]/40'
            }`}
          >
            <div className="w-11 h-11 rounded-xl bg-[#fff7d6] flex items-center justify-center shrink-0">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#efbf04" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/>
              </svg>
            </div>
            <div>
              <p className="font-bold font-[Alexandria]">Bank Transfer</p>
              <p className="text-xs text-gray-400 font-[Alexandria] mt-0.5">IBAN / SWIFT transfer</p>
            </div>
            {method === 'bank' && <div className="ml-auto w-2.5 h-2.5 rounded-full bg-[#efbf04]" />}
          </button>

          <button
            onClick={() => setMethod('solana')}
            className={`w-full flex items-center gap-4 p-5 rounded-2xl border-2 transition-all text-left ${
              method === 'solana'
                ? 'border-[#efbf04] bg-[#fffdf0] shadow-sm'
                : 'border-gray-100 bg-white hover:border-[#efbf04]/40'
            }`}
          >
            <div className="w-11 h-11 rounded-xl bg-[#fff7d6] flex items-center justify-center shrink-0">
              <svg width="22" height="22" viewBox="0 0 397.7 311.7" fill="none">
                <path d="M64.6 237.9a14 14 0 0 1 9.9-4.1h317.4c6.2 0 9.4 7.5 5 12L333 298.6a14 14 0 0 1-9.9 4.1H5.7c-6.2 0-9.4-7.5-5-12l63.9-52.8z" fill="#efbf04"/>
                <path d="M64.6 13.1A14.3 14.3 0 0 1 74.5 9h317.4c6.2 0 9.4 7.5 5 12L333 73.8a14 14 0 0 1-9.9 4.1H5.7c-6.2 0-9.4-7.5-5-12L64.6 13.1z" fill="#efbf04"/>
                <path d="M333 125.1a14 14 0 0 0-9.9-4.1H5.7c-6.2 0-9.4 7.5-5 12l63.9 52.8a14 14 0 0 0 9.9 4.1h317.4c6.2 0 9.4-7.5 5-12L333 125.1z" fill="#efbf04"/>
              </svg>
            </div>
            <div>
              <p className="font-bold font-[Alexandria]">Solana Withdraw</p>
              <p className="text-xs text-gray-400 font-[Alexandria] mt-0.5">Fast &amp; low fees</p>
            </div>
            {method === 'solana' && <div className="ml-auto w-2.5 h-2.5 rounded-full bg-[#efbf04]" />}
          </button>
        </div>

        {/* Right: details panel */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-col gap-5">
          {method === 'bank' ? (
            <>
              <div>
                <p className="text-xs text-gray-400 uppercase tracking-widest font-[Alexandria] mb-3">Bank Details</p>
                <div className="flex flex-col gap-3">
                  <input type="text" placeholder="Account holder name" className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm font-[Alexandria] outline-none focus:border-[#efbf04] transition-colors" />
                  <input type="text" placeholder="IBAN" className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm font-[Alexandria] outline-none focus:border-[#efbf04] transition-colors" />
                  <input type="text" placeholder="SWIFT / BIC" className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm font-[Alexandria] outline-none focus:border-[#efbf04] transition-colors" />
                  <input type="text" placeholder="Bank name" className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm font-[Alexandria] outline-none focus:border-[#efbf04] transition-colors" />
                  <input type="number" placeholder="Amount (coins)" value={amount} onChange={(e) => setAmount(e.target.value)} className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm font-[Alexandria] outline-none focus:border-[#efbf04] transition-colors" />
                </div>
              </div>
              <div className="bg-[#fff7d6] rounded-xl p-4 flex flex-col gap-1 text-xs font-[Alexandria]">
                <div className="flex justify-between text-gray-600"><span>Processing time</span><span className="font-bold text-gray-800">1–3 business days</span></div>
                <div className="flex justify-between text-gray-600"><span>Minimum withdrawal</span><span className="font-bold text-gray-800">500 coins</span></div>
                <div className="flex justify-between text-gray-600"><span>Fee</span><span className="font-bold text-gray-800">1.5%</span></div>
              </div>
              <button className="w-full py-3 rounded-xl bg-[#efbf04] hover:bg-[#d4a800] text-white font-bold font-[Alexandria] text-sm transition-all shadow-sm">
                Request Withdrawal
              </button>
            </>
          ) : (
            <>
              <div>
                <p className="text-xs text-gray-400 uppercase tracking-widest font-[Alexandria] mb-3">Your Solana Address</p>
                <input type="text" placeholder="Paste your SOL wallet address" className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm font-mono outline-none focus:border-[#efbf04] transition-colors" />
                <p className="text-[10px] text-gray-400 font-[Alexandria] mt-2">Double-check your address. Withdrawals to wrong addresses cannot be recovered.</p>
              </div>
              <div>
                <p className="text-xs text-gray-400 uppercase tracking-widest font-[Alexandria] mb-3">Amount</p>
                <input type="number" placeholder="Amount in SOL" value={amount} onChange={(e) => setAmount(e.target.value)} className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm font-[Alexandria] outline-none focus:border-[#efbf04] transition-colors" />
              </div>
              <div className="bg-[#fff7d6] rounded-xl p-4 flex flex-col gap-1 text-xs font-[Alexandria]">
                <div className="flex justify-between text-gray-600"><span>Network</span><span className="font-bold text-gray-800">Solana Mainnet</span></div>
                <div className="flex justify-between text-gray-600"><span>Estimated fee</span><span className="font-bold text-gray-800">~0.000005 SOL</span></div>
                <div className="flex justify-between text-gray-600"><span>Processing time</span><span className="font-bold text-gray-800">~30 seconds</span></div>
              </div>
              <button className="w-full py-3 rounded-xl bg-[#efbf04] hover:bg-[#d4a800] text-white font-bold font-[Alexandria] text-sm transition-all shadow-sm">
                Confirm Withdrawal
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
