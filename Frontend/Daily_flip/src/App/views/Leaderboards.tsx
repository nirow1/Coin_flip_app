export default function Leaderboards() {
  return (
    <div className="p-6 max-w-7xl text-gray-900">
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