import { useState } from 'react';
import { Home, Wallet, Gamepad2, Trophy, Users, ArrowDownToLine, ArrowUpFromLine, ChevronDown } from 'lucide-react';
import metalTexture from '../../imports/gold_diagonal.jpg';

interface SidebarProps {
  activeItem: string;
  onItemClick: (item: string) => void;
}

export default function Sidebar({ activeItem, onItemClick }: SidebarProps) {
  const [animatingItem, setAnimatingItem] = useState<string | null>(null);
  const [walletOpen, setWalletOpen] = useState(false);

  const menuItems = [
    { id: 'main', label: 'Main Page', icon: Home },
    { id: 'wallet', label: 'Start Wallet', icon: Wallet },
    { id: 'games', label: 'My Games', icon: Gamepad2 },
    { id: 'leaderboards', label: 'Leaderboards', icon: Trophy },
    { id: 'friends', label: 'Friends', icon: Users },
  ];

  const handleClick = (id: string) => {
    setAnimatingItem(id);
    onItemClick(id);
    if (id === 'wallet') setWalletOpen((prev) => !prev);
    setTimeout(() => setAnimatingItem(null), 600);
  };

  return (
    <aside className="w-64 bg-[#fbf8eb] flex flex-col shadow-sm">
      <style>{`
        @keyframes shine {
          0% {
            left: -100%;
          }
          100% {
            left: 100%;
          }
        }
        .shine-effect {
          position: relative;
          overflow: hidden;
        }
        .shine-effect::after {
          content: '';
          position: absolute;
          top: 0;
          left: -100%;
          width: 50%;
          height: 100%;
          background: linear-gradient(
            120deg,
            transparent,
            rgba(255, 255, 255, 0.6),
            transparent
          );
          animation: shine 1s ease-in-out;
        }
      `}</style>
      <nav className="flex-1 p-4 border-r border-gray-200 rounded-[9px] rounded-[10px]" style={{ background: '#F9F9F9' }}>
        <ul className="space-y-2">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeItem === item.id;
            const isAnimating = animatingItem === item.id;
            return (
              <li key={item.id}>
                <button
                  onClick={() => handleClick(item.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                    isActive
                      ? 'bg-[#FFFFFF] text-gray-900 shadow-md'
                      : 'text-gray-600 hover:text-[#432205] hover:bg-[#fbf8eb]'
                  } ${isAnimating ? 'shine-effect' : ''}`}
                >
                  <Icon size={20} />
                  <span className="font-[Alexandria] flex-1 text-left">{item.label}</span>
                  {item.id === 'wallet' && (
                    <ChevronDown
                      size={16}
                      className={`transition-transform duration-300 ${walletOpen ? 'rotate-180' : ''}`}
                    />
                  )}
                </button>
                {item.id === 'wallet' && walletOpen && (
                  <ul className="mt-1 ml-4 space-y-1 overflow-hidden">
                    <li>
                      <button
                        onClick={() => onItemClick('deposit')}
                        className="w-full flex items-center gap-3 px-4 py-2 rounded-lg text-sm text-gray-600 hover:text-[#432205] hover:bg-[#fbf8eb] transition-all font-[Alexandria]"
                      >
                        <ArrowDownToLine size={16} />
                        Deposit
                      </button>
                    </li>
                    <li>
                      <button
                        onClick={() => onItemClick('withdraw')}
                        className="w-full flex items-center gap-3 px-4 py-2 rounded-lg text-sm text-gray-600 hover:text-[#432205] hover:bg-[#fbf8eb] transition-all font-[Alexandria]"
                      >
                        <ArrowUpFromLine size={16} />
                        Withdraw
                      </button>
                    </li>
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}
