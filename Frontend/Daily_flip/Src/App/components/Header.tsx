import { useState } from 'react';
import { motion } from 'motion/react';

export default function Header() {
  const [isLogoutShining, setIsLogoutShining] = useState(false);

  const handleLogoutClick = () => {
    setIsLogoutShining(true);
    setTimeout(() => setIsLogoutShining(false), 600);
  };

  return (
    <header className="h-20 bg-white border-b border-gray-200 flex items-center justify-between px-6 shadow-sm bg-[#ffffff]">
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
          animation: shine 0.6s ease-in-out;
        }
      `}</style>
      <h1 className="text-2xl text-[#efbf04] flex items-center gap-2 font-[Audiowide]">
        <motion.span
          className="text-3xl inline-block"
          style={{ fontFamily: 'Apple Color Emoji, Segoe UI Emoji, Noto Color Emoji, sans-serif' }}
          animate={{ rotateY: 360 }}
          transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
        >
          🪙
        </motion.span>
        DailyFlip
      </h1>
      <div className="flex items-center gap-4">
        <div className="w-13 h-13 rounded-lg bg-[#efbf04] flex items-center justify-center shadow-md">
          
        </div>
        <div className="text-left">
          <div className="text-[#3c3c3c] font-bold font-[Alexandria]">Player_Gold123</div>
          <button
            onClick={handleLogoutClick}
            className={`text-sm hover:text-[#432205] transition-colors ${isLogoutShining ? 'shine-effect' : ''} text-[#4d4d4d] font-[Alexandria]`}
          >
            Logout
          </button>
        </div>
      </div>
    </header>
  );
}
