import { useState } from 'react';

export default function FriendsPage() {
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

const friendsData = [
  { id: 1, name: 'CryptoKing', status: 'online', credits: 142800, streak: 17, avatar: 'C' },
  { id: 2, name: 'LuckyFlip', status: 'online', credits: 98500, streak: 24, avatar: 'L' },
  { id: 3, name: 'GoldRush', status: 'offline', credits: 87200, streak: 19, avatar: 'G' },
  { id: 4, name: 'HeadsUp', status: 'online', credits: 74100, streak: 11, avatar: 'H' },
  { id: 5, name: 'CoinMaster', status: 'offline', credits: 61300, streak: 6, avatar: 'M' },
  { id: 6, name: 'DoubleDown', status: 'online', credits: 53700, streak: 8, avatar: 'D' },
  { id: 7, name: 'TailSpin', status: 'offline', credits: 44900, streak: 9, avatar: 'T' },
];
