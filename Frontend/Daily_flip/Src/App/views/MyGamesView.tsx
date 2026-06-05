export default function MyGames() {
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