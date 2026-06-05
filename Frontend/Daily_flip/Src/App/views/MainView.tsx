import { useState, useEffect } from 'react';
import { Clock, TrendingUp } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

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
            className="text-6xl text-[#ffcc00] font-bold font-[Bebas_Neue] tracking-[0.05em]"
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

const winningsData = [
  { name: 'Mon', Alice: 1200, Bob: 800, Carol: 600 },
  { name: 'Tue', Alice: 900, Bob: 1400, Carol: 1100 },
  { name: 'Wed', Alice: 1800, Bob: 700, Carol: 1300 },
  { name: 'Thu', Alice: 1500, Bob: 1100, Carol: 900 },
  { name: 'Fri', Alice: 2100, Bob: 1600, Carol: 1700 },
  { name: 'Sat', Alice: 1700, Bob: 2200, Carol: 2000 },
  { name: 'Sun', Alice: 2400, Bob: 1900, Carol: 2300 },
];

export default function MainView() {
  return (
    <div className="p-6 flex flex-col gap-6 max-w-5xl">
      <GameWidget />
      <div className="grid grid-cols-2 gap-6">
        <WinningsChart />
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 flex items-center justify-center min-h-[400px]">
          <p className="text-gray-300 font-[Alexandria] text-sm">Coming soon</p>
        </div>
      </div>
    </div>
  );
}
