import { useContext, useEffect, useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import {
  createQuote,
  createOrder,
  getOrder,
  type CreditsQuoteResponse,
  type CreateOrderResponse,
} from '../../Api/wallet';
import { GameContext } from '../../Context/GameContext';

type Step = 'credits' | 'quote' | 'pay' | 'paid';

function secondsUntil(iso: string): number {
  return Math.max(0, Math.floor((new Date(iso).getTime() - Date.now()) / 1000));
}

function formatCountdown(totalSec: number): string {
  const m = String(Math.floor(totalSec / 60)).padStart(2, '0');
  const s = String(totalSec % 60).padStart(2, '0');
  return `${m}:${s}`;
}

function errorMessage(err: unknown): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  return 'Something went wrong. Try again.';
}

export default function DepositPage() {
  const { refreshBalance } = useContext(GameContext);

  const [step, setStep] = useState<Step>('credits');
  const [creditsInput, setCreditsInput] = useState('');
  const [quote, setQuote] = useState<CreditsQuoteResponse | null>(null);
  const [order, setOrder] = useState<CreateOrderResponse | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [rail, setRail] = useState<'solana' | 'polygon'>('solana');

  const expiryIso =
    step === 'quote' ? quote?.expires_at : step === 'pay' ? order?.expires_at : undefined;

  useEffect(() => {
    if (!expiryIso) {
      setSecondsLeft(0);
      return;
    }
    const tick = () => setSecondsLeft(secondsUntil(expiryIso));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [expiryIso]);

  useEffect(() => {
    if (step !== 'pay' || !order) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await getOrder(order.order_id);
        if (cancelled) return;
        setStatus(res.data.status);
        if (res.data.status === 'paid') {
          await refreshBalance();
          setStep('paid');
        }
      } catch (err) {
        if (!cancelled) setError(errorMessage(err));
      }
    };
    void poll();
    const id = setInterval(() => void poll(), 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [step, order, refreshBalance]);

  const onGetQuote = async () => {
    const credits = Number(creditsInput);
    if (!Number.isInteger(credits) || credits < 1) {
      setError('Enter a whole number of credits (at least 1).');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await createQuote(credits);
      setQuote(res.data);
      setOrder(null);
      setStatus(null);
      setStep('quote');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const onCreateOrder = async () => {
    if (!quote) return;
    setBusy(true);
    setError(null);
    try {
      const res = await createOrder(quote.quote_id);
      setOrder(res.data);
      setStatus('pending');
      setStep('pay');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const onStartOver = () => {
    setStep('credits');
    setCreditsInput('');
    setQuote(null);
    setOrder(null);
    setStatus(null);
    setError(null);
  };

  return (
    <div className="p-6 max-w-7xl text-gray-900">
      <h2 className="text-3xl text-[#efbf04] mb-5 font-[Alexandria]">Deposit</h2>
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
              <p className="font-bold font-[Alexandria]">Polygon Deposit</p>
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
              <p className="font-bold font-[Alexandria]">Solana Deposit</p>
              <p className="text-xs text-gray-400 font-[Alexandria] mt-0.5">SOL only · fast &amp; low fees</p>
            </div>
            {rail === 'solana' && <div className="ml-auto w-2.5 h-2.5 rounded-full bg-[#efbf04]" />}
          </button>
        </div>

        {/* Right: details panel */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-col gap-5">
          {error && (
            <p className="text-sm text-red-600 font-[Alexandria]">{error}</p>
          )}

          {rail === 'polygon' ? (
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-widest font-[Alexandria] mb-3">
                Polygon
              </p>
              <p className="text-sm text-gray-600 font-[Alexandria]">
                Polygon deposits coming soon.
              </p>
            </div>
          ) : (
            <>
              {step === 'credits' && (
                <>
                  <div>
                    <p className="text-xs text-gray-400 uppercase tracking-widest font-[Alexandria] mb-3">
                      Credits
                    </p>
                    <input
                      type="number"
                      min={1}
                      step={1}
                      placeholder="How many credits?"
                      value={creditsInput}
                      onChange={(e) => setCreditsInput(e.target.value)}
                      className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm font-[Alexandria] outline-none focus:border-[#efbf04] transition-colors"
                    />
                    <p className="text-[10px] text-gray-400 font-[Alexandria] mt-2">
                      Pay with SOL only. Card and other chains are not supported here.
                    </p>
                  </div>
                  <button
                    onClick={onGetQuote}
                    disabled={busy}
                    className="w-full py-3 rounded-xl bg-[#efbf04] hover:bg-[#d4a800] disabled:opacity-60 text-white font-bold font-[Alexandria] text-sm transition-all shadow-sm"
                  >
                    Get quote
                  </button>
                </>
              )}

              {step === 'quote' && quote && (
                <>
                  <div>
                    <p className="text-xs text-gray-400 uppercase tracking-widest font-[Alexandria] mb-3">
                      Quote
                    </p>
                    <div className="bg-[#fff7d6] rounded-xl p-4 flex flex-col gap-1 text-xs font-[Alexandria]">
                      <div className="flex justify-between text-gray-600">
                        <span>Credits</span>
                        <span className="font-bold text-gray-800">{quote.credits}</span>
                      </div>
                      <div className="flex justify-between text-gray-600">
                        <span>SOL to send</span>
                        <span className="font-bold text-gray-800">{quote.amount_sol} SOL</span>
                      </div>
                      <div className="flex justify-between text-gray-600">
                        <span>Included fee</span>
                        <span className="font-bold text-gray-800">
                          {(Number(quote.fee) * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="flex justify-between text-gray-600">
                        <span>Network</span>
                        <span className="font-bold text-gray-800">{quote.cluster}</span>
                      </div>
                      <div className="flex justify-between text-gray-600">
                        <span>Valid for</span>
                        <span className="font-bold text-gray-800">
                          {formatCountdown(secondsLeft)}
                        </span>
                      </div>
                    </div>
                    <p className="text-[10px] text-gray-400 font-[Alexandria] mt-2">
                      SOL only. Confirm before the timer runs out.
                    </p>
                  </div>
                  <div className="flex flex-col gap-2">
                    <button
                      onClick={onCreateOrder}
                      disabled={busy || secondsLeft === 0}
                      className="w-full py-3 rounded-xl bg-[#efbf04] hover:bg-[#d4a800] disabled:opacity-60 text-white font-bold font-[Alexandria] text-sm transition-all shadow-sm"
                    >
                      Confirm order
                    </button>
                    <button
                      onClick={onStartOver}
                      disabled={busy}
                      className="w-full py-3 rounded-xl bg-white border border-gray-200 hover:bg-[#fbf8eb] hover:border-[#efbf04] disabled:opacity-60 text-gray-800 font-bold font-[Alexandria] text-sm transition-all shadow-sm"
                    >
                      Cancel
                    </button>
                  </div>
                </>
              )}

              {step === 'pay' && order && (
                <>
                  <div>
                    <p className="text-xs text-gray-400 uppercase tracking-widest font-[Alexandria] mb-3">
                      Pay with Solana
                    </p>
                    <div className="flex flex-col items-center gap-4">
                      <div className="bg-white p-3 rounded-xl border border-gray-100">
                        <QRCodeSVG value={order.solana_pay_url} size={200} />
                      </div>
                      <a
                        href={order.solana_pay_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-bold font-[Alexandria] text-[#efbf04] hover:text-[#d4a800] underline underline-offset-2"
                      >
                        Open in wallet
                      </a>
                    </div>
                  </div>
                  <div className="bg-[#fff7d6] rounded-xl p-4 flex flex-col gap-1 text-xs font-[Alexandria]">
                    <div className="flex justify-between text-gray-600">
                      <span>Amount</span>
                      <span className="font-bold text-gray-800">{order.amount_sol} SOL</span>
                    </div>
                    <div className="flex justify-between text-gray-600">
                      <span>Status</span>
                      <span className="font-bold text-gray-800">
                        {status ?? 'pending'}
                      </span>
                    </div>
                    <div className="flex justify-between text-gray-600">
                      <span>Expires in</span>
                      <span className="font-bold text-gray-800">
                        {formatCountdown(secondsLeft)}
                      </span>
                    </div>
                  </div>
                  <p className="text-[10px] text-gray-400 font-[Alexandria]">
                    Waiting for payment on Solana. This page checks every few seconds.
                  </p>
                  <button
                    onClick={onStartOver}
                    className="w-full py-3 rounded-xl bg-white border border-gray-200 hover:bg-[#fbf8eb] hover:border-[#efbf04] text-gray-800 font-bold font-[Alexandria] text-sm transition-all shadow-sm"
                  >
                    Cancel
                  </button>
                </>
              )}

              {step === 'paid' && (
                <>
                  <div>
                    <p className="text-xs text-gray-400 uppercase tracking-widest font-[Alexandria] mb-3">
                      Paid
                    </p>
                    <p className="text-sm font-[Alexandria] text-gray-700">
                      Payment received
                      {quote ? ` — ${quote.credits} credits added.` : '.'} Your balance
                      is updated.
                    </p>
                  </div>
                  <button
                    onClick={onStartOver}
                    className="w-full py-3 rounded-xl bg-[#efbf04] hover:bg-[#d4a800] text-white font-bold font-[Alexandria] text-sm transition-all shadow-sm"
                  >
                    Deposit again
                  </button>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
