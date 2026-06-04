import { useState, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import CoinFlip from './components/CoinFlip';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Clock, TrendingUp, ArrowDownToLine, ArrowUpFromLine } from 'lucide-react';

const winningsData = [
  { name: 'Mon', Alice: 1200, Bob: 800, Carol: 600 },
  { name: 'Tue', Alice: 900, Bob: 1400, Carol: 1100 },
  { name: 'Wed', Alice: 1800, Bob: 700, Carol: 1300 },
  { name: 'Thu', Alice: 1500, Bob: 1100, Carol: 900 },
  { name: 'Fri', Alice: 2100, Bob: 1600, Carol: 1700 },
  { name: 'Sat', Alice: 1700, Bob: 2200, Carol: 2000 },
  { name: 'Sun', Alice: 2400, Bob: 1900, Carol: 2300 },
];

function useCountdown(target: number) {
  const [timeLeft, setTimeLeft] = useState(target);
  useEffect(() => {
    const id = setInterval(() => setTimeLeft((t) => Math.max(0, t - 1)), 1000);
    return () => clearInterval(id);
  }, []);
  const m = String(Math.floor(timeLeft / 60)).padStart(2, '0');
  const s = String(timeLeft % 60).padStart(2, '0');
  return `${m}:${s}`;
}

function GameWidget() {
  const countdown = useCountdown(847);
  const [joined, setJoined] = useState(false);
  const [animating, setAnimating] = useState(false);

  const handleJoin = () => {
    setAnimating(true);
    setTimeout(() => { setJoined(true); setAnimating(false); }, 600);
  };

  return (
    <div className="bg-[#fcfcfc] rounded-2xl shadow-sm border-8 border-[#fff] overflow-hidden">
      {/* Top bar: round info left */}
      <div className="px-5 pt-5 pb-0 flex items-start bg-[#00000000]">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest font-[Alexandria] text-[#000000]">Live Round</p>
          <p className="text-lg font-bold font-[Alexandria] text-[#efbf04]">#2847</p>
        </div>
      </div>

      {/* Center: prize + timer + button */}
      <div className="flex flex-col items-center gap-5 px-5 py-8">
        {/* Prize */}
        <div className="text-center">
          <p className="text-xs text-gray-400 uppercase tracking-widest font-[Alexandria] mb-1">Prize Pool</p>
          <p
            className="text-6xl text-[#ffcc00] font-bold"
            style={{ fontFamily: '"Bebas Neue", cursive', letterSpacing: '0.05em' }}
          >
            8,500
          </p>
          <p className="text-sm text-gray-400 font-[Alexandria] mt-1">coins</p>
        </div>

        {/* Timer */}
        <div className="flex items-center gap-2 bg-gray-50 rounded-xl px-5 py-2.5">
          <Clock size={15} className="text-[#efbf04]" />
          <span className="font-mono font-bold text-xl text-gray-800">{countdown}</span>
        </div>

        {/* Join button */}
        <button
          onClick={handleJoin}
          disabled={joined}
          className={`relative w-[300px] py-3 rounded-xl font-bold font-[Alexandria] text-sm transition-all overflow-hidden
            ${joined
              ? 'bg-green-50 text-green-600 border border-green-200 cursor-default'
              : 'bg-[#efbf04] hover:bg-[#d4a800] text-white shadow-md hover:shadow-lg active:scale-[0.98]'
            } ${animating ? 'shine-effect' : ''}`}
        >
          <span className="relative z-10">
            {joined ? '✓ Joined — Good luck!' : 'Join Game'}
          </span>
        </button>
      </div>
    </div>
  );
}

function WinningsChart() {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
      <div className="p-5 border-b border-gray-50 flex items-center gap-3">
        <div className="w-9 h-9 rounded-full bg-[#fff7d6] flex items-center justify-center">
          <TrendingUp size={18} className="text-[#efbf04]" />
        </div>
        <div>
          <h3 className="font-bold text-gray-900 font-[Alexandria]">Player Winnings</h3>
          <p className="text-xs text-gray-400 font-[Alexandria]">Last 7 days — top players</p>
        </div>
        <div className="ml-auto flex items-center gap-4 text-xs font-[Alexandria]">
          
          
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#432205] inline-block" />Carol</span>
        </div>
      </div>
      <div className="p-5">
        <ResponsiveContainer width="100%" height={220}>
          <LineChart id="winnings-chart" data={winningsData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f3f3f3" />
            <XAxis dataKey="name" tick={{ fontSize: 12, fontFamily: 'Alexandria', fill: '#9ca3af' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 12, fontFamily: 'Alexandria', fill: '#9ca3af' }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{ borderRadius: 10, border: '1px solid #f3f3f3', fontFamily: 'Alexandria', fontSize: 12 }}
              formatter={(v: number) => [`${v.toLocaleString()} coins`]}
            />
            <Line type="monotone" dataKey="Alice" stroke="#efbf04" strokeWidth={2.5} dot={false} />
            <Line type="monotone" dataKey="Bob" stroke="#94a3b8" strokeWidth={2.5} dot={false} />
            <Line type="monotone" dataKey="Carol" stroke="#432205" strokeWidth={2.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

const myGamesData = [
  { id: 'GF-2841', prizePool: '12,400', heads: 62, tails: 38, status: 'Live', img: 'https://images.unsplash.com/photo-1624365169106-1f1f4cd65c91?w=160&h=100&fit=crop' },
  { id: 'GF-2799', prizePool: '5,200', heads: 45, tails: 55, status: 'Ended', img: 'https://images.unsplash.com/photo-1624365168012-7ed139887755?w=160&h=100&fit=crop' },
  { id: 'GF-2755', prizePool: '8,900', heads: 50, tails: 50, status: 'Won', img: 'https://images.unsplash.com/photo-1589180176337-503fed4bcfe0?w=160&h=100&fit=crop' },
  { id: 'GF-2710', prizePool: '3,100', heads: 33, tails: 67, status: 'Lost', img: 'https://images.unsplash.com/photo-1624365169106-1f1f4cd65c91?w=160&h=100&fit=crop' },
];

const statusStyle: Record<string, string> = {
  Live: 'bg-green-100 text-green-700',
  Ended: 'bg-gray-100 text-gray-500',
  Won: 'bg-[#fff7d6] text-[#7a4f00]',
  Lost: 'bg-red-50 text-red-500',
};

function MyGames() {
  return (
    <div className="p-6 text-gray-900">
      <h2 className="text-3xl text-[#efbf04] mb-5 font-[Alexandria]">My Games</h2>
      <div className="flex flex-col gap-3 max-w-5xl">
        {myGamesData.map((game) => (
          <div
            key={game.id}
            className="bg-white border border-gray-100 rounded-2xl shadow-sm flex items-center overflow-hidden h-[100px]"
          >
            {/* Left image */}
            <img
              src={game.img}
              alt="game"
              className="h-full w-[120px] object-cover shrink-0"
            />

            {/* Middle info */}
            <div className="flex-1 px-5 flex flex-col gap-1.5 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-bold text-gray-800 font-[Alexandria] text-sm">{game.id}</span>
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full font-[Alexandria] ${statusStyle[game.status]}`}>
                  {game.status}
                </span>
              </div>
              <p className="text-xs text-gray-400 font-[Alexandria]">
                Prize pool: <span className="text-[#efbf04] font-semibold">{game.prizePool} coins</span>
              </p>
              {/* Heads / tails bar */}
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-gray-400 font-[Alexandria] w-12">H {game.heads}%</span>
                <div className="flex-1 h-2 rounded-full overflow-hidden flex gap-px">
                  <div className="bg-[#efbf04] rounded-full" style={{ width: `${game.heads}%` }} />
                  <div className="bg-slate-300 rounded-full flex-1" />
                </div>
                <span className="text-[10px] text-gray-400 font-[Alexandria] w-12 text-right">T {game.tails}%</span>
              </div>
            </div>

            {/* Right button */}
            <div className="px-4 shrink-0">
              <button className="px-4 py-2 rounded-xl bg-[#efbf04] hover:bg-[#d4a800] text-white text-xs font-bold font-[Alexandria] transition-all shadow-sm whitespace-nowrap">
                Game Details
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DepositPage() {
  const [method, setMethod] = useState<'card' | 'solana'>('card');
  const [amount, setAmount] = useState('');
  const solanaAddress = 'DailyFlip7xK3mN9pQrZ2wVbLcUoYsAeGhJfTiXvBnRd';

  return (
    <div className="p-6 max-w-5xl text-gray-900">
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

const creditsData = [
  { rank: 1, name: 'CryptoKing', avatar: 'C', credits: 142800 },
  { rank: 2, name: 'LuckyFlip', avatar: 'L', credits: 98500 },
  { rank: 3, name: 'GoldRush', avatar: 'G', credits: 87200 },
  { rank: 4, name: 'HeadsUp', avatar: 'H', credits: 74100 },
  { rank: 5, name: 'CoinMaster', avatar: 'M', credits: 61300 },
  { rank: 6, name: 'DoubleDown', avatar: 'D', credits: 53700 },
  { rank: 7, name: 'TailSpin', avatar: 'T', credits: 44900 },
  { rank: 8, name: 'FlipPro', avatar: 'F', credits: 38200 },
];

const streakData = [
  { rank: 1, name: 'LuckyFlip', avatar: 'L', streak: 24 },
  { rank: 2, name: 'GoldRush', avatar: 'G', streak: 19 },
  { rank: 3, name: 'CryptoKing', avatar: 'C', streak: 17 },
  { rank: 4, name: 'FlipPro', avatar: 'F', streak: 14 },
  { rank: 5, name: 'HeadsUp', avatar: 'H', streak: 11 },
  { rank: 6, name: 'TailSpin', avatar: 'T', streak: 9 },
  { rank: 7, name: 'DoubleDown', avatar: 'D', streak: 8 },
  { rank: 8, name: 'CoinMaster', avatar: 'M', streak: 6 },
];

const rankColor = (rank: number) => {
  if (rank === 1) return 'text-[#efbf04]';
  if (rank === 2) return 'text-slate-400';
  if (rank === 3) return 'text-amber-700';
  return 'text-gray-400';
};

const friendsData = [
  { id: 1, name: 'CryptoKing', status: 'online', credits: 142800, streak: 17, avatar: 'C' },
  { id: 2, name: 'LuckyFlip', status: 'online', credits: 98500, streak: 24, avatar: 'L' },
  { id: 3, name: 'GoldRush', status: 'offline', credits: 87200, streak: 19, avatar: 'G' },
  { id: 4, name: 'HeadsUp', status: 'online', credits: 74100, streak: 11, avatar: 'H' },
  { id: 5, name: 'CoinMaster', status: 'offline', credits: 61300, streak: 6, avatar: 'M' },
  { id: 6, name: 'DoubleDown', status: 'online', credits: 53700, streak: 8, avatar: 'D' },
  { id: 7, name: 'TailSpin', status: 'offline', credits: 44900, streak: 9, avatar: 'T' },
];

function FriendsPage() {
  const [search, setSearch] = useState('');
  const filtered = friendsData.filter((f) =>
    f.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-6 max-w-5xl text-gray-900">
      <h2 className="text-3xl text-[#efbf04] mb-5 font-[Alexandria]">Friends</h2>

      {/* Search bar */}
      <div className="flex gap-3 mb-5">
        <div className="flex-1 relative">
          <svg className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          <input
            type="text"
            placeholder="Search friends..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-3 bg-white border border-gray-200 rounded-xl text-sm font-[Alexandria] outline-none focus:border-[#efbf04] transition-colors"
          />
        </div>
        <button className="flex items-center gap-2 px-5 py-3 rounded-xl bg-[#efbf04] hover:bg-[#d4a800] text-white font-bold font-[Alexandria] text-sm shadow-sm transition-all active:scale-[0.98]">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/></svg>
          Add Friend
        </button>
      </div>

      {/* Friends list */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-50">
          <p className="text-xs text-gray-400 font-[Alexandria]">{filtered.length} friends</p>
        </div>
        {filtered.length === 0 ? (
          <p className="px-5 py-8 text-center text-gray-300 text-sm font-[Alexandria]">No friends found</p>
        ) : (
          <ul>
            {filtered.map((f, i) => (
              <li key={f.id} className={`flex items-center gap-4 px-5 py-4 hover:bg-[#fffdf0] transition-colors ${i < filtered.length - 1 ? 'border-b border-gray-50' : ''}`}>
                {/* Avatar + status dot */}
                <div className="relative shrink-0">
                  <div className="w-10 h-10 rounded-full bg-[#efbf04]/20 flex items-center justify-center font-bold text-[#7a4f00] font-[Alexandria]">
                    {f.avatar}
                  </div>
                  <span className={`absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full border-2 border-white ${f.status === 'online' ? 'bg-green-400' : 'bg-gray-300'}`} />
                </div>

                {/* Name + status */}
                <div className="flex-1 min-w-0">
                  <p className="font-bold text-sm text-gray-900 font-[Alexandria]">{f.name}</p>
                  <p className={`text-xs font-[Alexandria] ${f.status === 'online' ? 'text-green-500' : 'text-gray-400'}`}>
                    {f.status === 'online' ? 'Online' : 'Offline'}
                  </p>
                </div>

                {/* Stats */}
                <div className="flex items-center gap-6 text-sm font-[Alexandria] text-right">
                  <div>
                    <p className="text-xs text-gray-400">Credits</p>
                    <p className="font-bold text-[#efbf04]">{f.credits.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400">Best streak</p>
                    <p className="font-bold text-gray-800">{f.streak} wins</p>
                  </div>
                </div>

                {/* Challenge button */}
                <button className="ml-2 px-4 py-2 rounded-xl border border-[#efbf04] text-[#efbf04] hover:bg-[#efbf04] hover:text-white font-bold font-[Alexandria] text-xs transition-all shrink-0">
                  Challenge
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function Leaderboards() {
  return (
    <div className="p-6 max-w-5xl text-gray-900">
      <h2 className="text-3xl text-[#efbf04] mb-5 font-[Alexandria]">Leaderboards</h2>
      <div className="grid grid-cols-2 gap-5">

        {/* Total Credits Won */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-50 flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-[#fff7d6] flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#efbf04" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg>
            </div>
            <div>
              <p className="font-bold text-gray-900 font-[Alexandria]">Total Credits Won</p>
              <p className="text-xs text-gray-400 font-[Alexandria]">All time</p>
            </div>
          </div>
          <table className="w-full">
            <thead>
              <tr className="text-xs text-gray-400 font-[Alexandria] border-b border-gray-50">
                <th className="px-5 py-2.5 text-left w-8">#</th>
                <th className="px-2 py-2.5 text-left">Player</th>
                <th className="px-5 py-2.5 text-right">Credits</th>
              </tr>
            </thead>
            <tbody>
              {creditsData.map((p) => (
                <tr key={p.rank} className="border-b border-gray-50 last:border-0 hover:bg-[#fffdf0] transition-colors">
                  <td className={`px-5 py-3 font-bold font-[Alexandria] text-sm ${rankColor(p.rank)}`}>{p.rank}</td>
                  <td className="px-2 py-3">
                    <div className="flex items-center gap-2.5">
                      <div className="w-7 h-7 rounded-full bg-[#efbf04]/20 flex items-center justify-center text-xs font-bold text-[#7a4f00] font-[Alexandria]">{p.avatar}</div>
                      <span className="text-sm font-[Alexandria] text-gray-800">{p.name}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3 text-right text-sm font-bold font-[Alexandria] text-[#efbf04]">{p.credits.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Longest Streak */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-50 flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-[#fff7d6] flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#efbf04" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
            </div>
            <div>
              <p className="font-bold text-gray-900 font-[Alexandria]">Longest Win Streak</p>
              <p className="text-xs text-gray-400 font-[Alexandria]">All time</p>
            </div>
          </div>
          <table className="w-full">
            <thead>
              <tr className="text-xs text-gray-400 font-[Alexandria] border-b border-gray-50">
                <th className="px-5 py-2.5 text-left w-8">#</th>
                <th className="px-2 py-2.5 text-left">Player</th>
                <th className="px-5 py-2.5 text-right">Streak</th>
              </tr>
            </thead>
            <tbody>
              {streakData.map((p) => (
                <tr key={p.rank} className="border-b border-gray-50 last:border-0 hover:bg-[#fffdf0] transition-colors">
                  <td className={`px-5 py-3 font-bold font-[Alexandria] text-sm ${rankColor(p.rank)}`}>{p.rank}</td>
                  <td className="px-2 py-3">
                    <div className="flex items-center gap-2.5">
                      <div className="w-7 h-7 rounded-full bg-[#efbf04]/20 flex items-center justify-center text-xs font-bold text-[#7a4f00] font-[Alexandria]">{p.avatar}</div>
                      <span className="text-sm font-[Alexandria] text-gray-800">{p.name}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3 text-right text-sm font-bold font-[Alexandria] text-[#efbf04]">{p.streak} wins</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

      </div>
    </div>
  );
}

function WithdrawPage() {
  const [method, setMethod] = useState<'bank' | 'solana'>('bank');
  const [amount, setAmount] = useState('');

  return (
    <div className="p-6 max-w-5xl text-gray-900">
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

export default function App() {
  const [activeItem, setActiveItem] = useState('main');

  return (
    <div className="size-full flex flex-col bg-white">
      <Header />
      <div className="flex-1 flex overflow-hidden">
        <Sidebar activeItem={activeItem} onItemClick={setActiveItem} />
        <main className="flex-1 overflow-auto bg-[#fbf8eb]">
          {activeItem === 'main' && (
            <div className="p-6 flex flex-col gap-6 max-w-5xl">
              <GameWidget />
              <div className="grid grid-cols-2 gap-6">
                <WinningsChart />
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 flex items-center justify-center min-h-[400px]">
                  <p className="text-gray-300 font-[Alexandria] text-sm">Coming soon</p>
                </div>
              </div>
            </div>
          )}
          {activeItem === 'wallet' && (
            <div className="p-8 text-gray-900 max-w-5xl">
              <h2 className="text-3xl text-[#efbf04] mb-4 font-[Alexandria]">Wallet</h2>
              <div className="bg-white border border-gray-100 rounded-2xl shadow-sm overflow-hidden">
                <div className="p-6 border-b border-gray-50">
                  <p className="text-xl font-bold font-[Alexandria]">Balance: <span className="text-[#efbf04]">1,000 credits</span></p>
                </div>
                <div className="p-4">
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart id="wallet-chart" data={[
                      { day: 'Mon', balance: 600 },
                      { day: 'Tue', balance: 850 },
                      { day: 'Wed', balance: 700 },
                      { day: 'Thu', balance: 1100 },
                      { day: 'Fri', balance: 950 },
                      { day: 'Sat', balance: 1300 },
                      { day: 'Sun', balance: 1000 },
                    ]} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f3f3f3" />
                      <XAxis dataKey="day" tick={{ fontSize: 11, fontFamily: 'Alexandria', fill: '#9ca3af' }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 11, fontFamily: 'Alexandria', fill: '#9ca3af' }} axisLine={false} tickLine={false} />
                      <Tooltip
                        contentStyle={{ borderRadius: 10, border: '1px solid #f3f3f3', fontFamily: 'Alexandria', fontSize: 12 }}
                        formatter={(v: number) => [`${v.toLocaleString()} coins`]}
                      />
                      <Line type="monotone" dataKey="balance" stroke="#efbf04" strokeWidth={2.5} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="flex justify-around mt-4">
                <button onClick={() => setActiveItem('deposit')} className="flex items-center justify-center gap-2 w-[300px] py-4 rounded-xl bg-[#efbf04] hover:bg-[#d4a800] text-white font-bold font-[Alexandria] shadow-sm transition-all active:scale-[0.98] text-[20px]">
                  <ArrowDownToLine size={20} />
                  Deposit
                </button>
                <button onClick={() => setActiveItem('withdraw')} className="flex items-center justify-center gap-2 w-[300px] py-4 rounded-xl bg-white border border-gray-200 hover:bg-[#fbf8eb] hover:border-[#efbf04] text-gray-800 hover:text-[#432205] font-bold font-[Alexandria] shadow-sm transition-all active:scale-[0.98] text-[20px]">
                  <ArrowUpFromLine size={20} />
                  Withdraw
                </button>
              </div>
            </div>
          )}
          {activeItem === 'deposit' && <DepositPage />}
          {activeItem === 'withdraw' && <WithdrawPage />}
          {activeItem === 'games' && <MyGames />}
          {activeItem === 'leaderboards' && <Leaderboards />}
          {activeItem === 'friends' && <FriendsPage />}
        </main>
      </div>
    </div>
  );
}