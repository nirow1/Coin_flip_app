import { useState } from 'react';

export default function WithdrawPage() {
  const [rail, setRail] = useState<'solana' | 'polygon'>('solana');

  return (
    <div className="p-6 max-w-7xl text-gray-900">
      <h2 className="text-3xl text-[#efbf04] mb-5 font-[Alexandria]">Withdraw</h2>
      <div className="grid grid-cols-2 gap-5 items-start">

        {/* Left: method selector */}
        <div className="flex flex-col gap-3">
          <button
            onClick={() => setRail('polygon')}
            className={`w-full flex items-center gap-4 p-5 rounded-2xl border-2 transition-all text-left ${
              rail === 'polygon'
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
              <p className="font-bold font-[Alexandria]">Polygon Withdraw</p>
              <p className="text-xs text-gray-400 font-[Alexandria] mt-0.5">USDC · coming soon</p>
            </div>
            {rail === 'polygon' && <div className="ml-auto w-2.5 h-2.5 rounded-full bg-[#efbf04]" />}
          </button>

          <button
            onClick={() => setRail('solana')}
            className={`w-full flex items-center gap-4 p-5 rounded-2xl border-2 transition-all text-left ${
              rail === 'solana'
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
              <p className="text-xs text-gray-400 font-[Alexandria] mt-0.5">Coming soon</p>
            </div>
            {rail === 'solana' && <div className="ml-auto w-2.5 h-2.5 rounded-full bg-[#efbf04]" />}
          </button>
        </div>

        {/* Right: details panel */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-col gap-5">
          {rail === 'polygon' ? (
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-widest font-[Alexandria] mb-3">
                Polygon
              </p>
              <p className="text-sm text-gray-600 font-[Alexandria]">
                Polygon withdrawals coming soon.
              </p>
            </div>
          ) : (
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-widest font-[Alexandria] mb-3">
                Solana
              </p>
              <p className="text-sm text-gray-600 font-[Alexandria]">
                Withdrawals coming soon.
              </p>
              <p className="text-[10px] text-gray-400 font-[Alexandria] mt-2">
                Solana payouts are built on the backend but not enabled yet.
              </p>
              <button
                type="button"
                disabled
                className="mt-4 w-full py-3 rounded-xl bg-[#efbf04] text-white font-bold font-[Alexandria] text-sm shadow-sm opacity-60 cursor-not-allowed"
              >
                Withdrawals coming soon
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
