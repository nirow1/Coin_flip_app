import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { ArrowDownToLine, ArrowUpFromLine } from 'lucide-react';

interface WalletViewProps {
  onNavigate: (item: string) => void;
}

export default function WalletView({ onNavigate }: WalletViewProps) {
  return (
    <div className="p-8 text-gray-900 max-w-7xl">
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
        <button onClick={() => onNavigate('deposit')} className="flex items-center justify-center gap-2 w-[300px] py-4 rounded-xl bg-[#efbf04] hover:bg-[#d4a800] text-white font-bold font-[Alexandria] shadow-sm transition-all active:scale-[0.98] text-[20px]">
          <ArrowDownToLine size={20} />
          Deposit
        </button>
        <button onClick={() => onNavigate('withdraw')} className="flex items-center justify-center gap-2 w-[300px] py-4 rounded-xl bg-white border border-gray-200 hover:bg-[#fbf8eb] hover:border-[#efbf04] text-gray-800 hover:text-[#432205] font-bold font-[Alexandria] shadow-sm transition-all active:scale-[0.98] text-[20px]">
          <ArrowUpFromLine size={20} />
          Withdraw
        </button>
      </div>
    </div>
  );
}
