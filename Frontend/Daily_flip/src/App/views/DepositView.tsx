import { useState } from 'react';

export default function DepositPage() {
  const [method, setMethod] = useState<'card' | 'solana'>('card');
  const [amount, setAmount] = useState('');
  const solanaAddress = 'DailyFlip7xK3mN9pQrZ2wVbLcUoYsAeGhJfTiXvBnRd';

  return (
    <div className="p-6 max-w-7xl text-gray-900">
      <h2 className="text-3xl text-[#efbf04] mb-5 font-[Alexandria]">Deposit</h2>
      <div className="grid grid-cols-2 gap-5 items-start">

        {/* Left: method selector */}
        <div className="flex flex-col gap-3">
          <button
            onClick={() => setMethod('card')}
            className={`w-full flex items-center gap-4 p-5 rounded-2xl border-2 transition-all text-left ${
              method === 'card'
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
              <p className="font-bold font-[Alexandria]">Card Deposit</p>
              <p className="text-xs text-gray-400 font-[Alexandria] mt-0.5">Visa, Mastercard, AMEX</p>
            </div>
            {method === 'card' && <div className="ml-auto w-2.5 h-2.5 rounded-full bg-[#efbf04]" />}
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
              <p className="font-bold font-[Alexandria]">Solana Deposit</p>
              <p className="text-xs text-gray-400 font-[Alexandria] mt-0.5">Fast &amp; low fees</p>
            </div>
            {method === 'solana' && <div className="ml-auto w-2.5 h-2.5 rounded-full bg-[#efbf04]" />}
          </button>
        </div>

        {/* Right: details panel */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-col gap-5">
          {method === 'card' ? (
            <>
              <div>
                <p className="text-xs text-gray-400 uppercase tracking-widest font-[Alexandria] mb-3">Card Details</p>
                <div className="flex flex-col gap-3">
                  <input
                    type="text"
                    placeholder="Cardholder name"
                    className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm font-[Alexandria] outline-none focus:border-[#efbf04] transition-colors"
                  />
                  <input
                    type="text"
                    placeholder="Card number"
                    maxLength={19}
                    className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm font-[Alexandria] outline-none focus:border-[#efbf04] transition-colors"
                  />
                  <div className="grid grid-cols-2 gap-3">
                    <input
                      type="text"
                      placeholder="MM / YY"
                      className="border border-gray-200 rounded-xl px-4 py-3 text-sm font-[Alexandria] outline-none focus:border-[#efbf04] transition-colors"
                    />
                    <input
                      type="text"
                      placeholder="CVV"
                      maxLength={4}
                      className="border border-gray-200 rounded-xl px-4 py-3 text-sm font-[Alexandria] outline-none focus:border-[#efbf04] transition-colors"
                    />
                  </div>
                  <input
                    type="number"
                    placeholder="Amount (coins)"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm font-[Alexandria] outline-none focus:border-[#efbf04] transition-colors"
                  />
                </div>
              </div>
              <button className="w-full py-3 rounded-xl bg-[#efbf04] hover:bg-[#d4a800] text-white font-bold font-[Alexandria] text-sm transition-all shadow-sm">
                Pay Now
              </button>
            </>
          ) : (
            <>
              <div>
                <p className="text-xs text-gray-400 uppercase tracking-widest font-[Alexandria] mb-3">Solana Wallet Address</p>
                <div className="bg-[#fbf8eb] rounded-xl p-4 break-all font-mono text-xs text-gray-700 select-all">
                  {solanaAddress}
                </div>
                <p className="text-[10px] text-gray-400 font-[Alexandria] mt-2">Send only SOL or SPL tokens to this address. Other assets will be lost.</p>
              </div>
              <div>
                <p className="text-xs text-gray-400 uppercase tracking-widest font-[Alexandria] mb-3">Amount</p>
                <input
                  type="number"
                  placeholder="Amount in SOL"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm font-[Alexandria] outline-none focus:border-[#efbf04] transition-colors"
                />
              </div>
              <div className="bg-[#fff7d6] rounded-xl p-4 flex flex-col gap-1 text-xs font-[Alexandria]">
                <div className="flex justify-between text-gray-600"><span>Network</span><span className="font-bold text-gray-800">Solana Mainnet</span></div>
                <div className="flex justify-between text-gray-600"><span>Estimated fee</span><span className="font-bold text-gray-800">~0.000005 SOL</span></div>
                <div className="flex justify-between text-gray-600"><span>Confirmations needed</span><span className="font-bold text-gray-800">1</span></div>
              </div>
              <button className="w-full py-3 rounded-xl bg-[#efbf04] hover:bg-[#d4a800] text-white font-bold font-[Alexandria] text-sm transition-all shadow-sm">
                Confirm Deposit
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
