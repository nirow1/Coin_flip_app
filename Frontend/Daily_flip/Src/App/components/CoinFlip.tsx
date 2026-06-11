import { useState } from 'react';
import { motion } from 'motion/react';

export default function CoinFlip() {
  const [isFlipping, setIsFlipping] = useState(false);
  const [result, setResult] = useState<'heads' | 'tails' | null>(null);
  const [isShining, setIsShining] = useState(false);

  const flipCoin = () => {
    setIsFlipping(true);
    setResult(null);
    setIsShining(true);
    setTimeout(() => setIsShining(false), 600);

    setTimeout(() => {
      const outcome = Math.random() > 0.5 ? 'heads' : 'tails';
      setResult(outcome);
      setIsFlipping(false);
    }, 1500);
  };

  return (
    <div className="flex flex-col items-center justify-center gap-8 py-12">
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
      <h2 className="text-4xl text-[#efbf04]">Flip the Coin</h2>

      <motion.div
        className="relative w-48 h-48 cursor-pointer"
        onClick={!isFlipping ? flipCoin : undefined}
        animate={isFlipping ? { rotateY: 1080 } : {}}
        transition={{ duration: 1.5, ease: 'easeInOut' }}
      >
        <div className="w-full h-full rounded-full bg-[#efbf04] shadow-2xl shadow-[#efbf04]/50 flex items-center justify-center">
          <span className="text-6xl">
            {!isFlipping && result === 'heads' && '👑'}
            {!isFlipping && result === 'tails' && '🪙'}
            {!isFlipping && !result && '🪙'}
            {isFlipping && '🌟'}
          </span>
        </div>
      </motion.div>

      {result && !isFlipping && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-3xl text-gray-900"
        >
          Result: <span className="text-[#efbf04] capitalize">{result}</span>
        </motion.div>
      )}

      <button
        onClick={flipCoin}
        disabled={isFlipping}
        className={`px-8 py-4 bg-[#efbf04] text-white rounded-lg hover:bg-[#fbf8eb] hover:text-[#432205] hover:shadow-lg hover:shadow-[#efbf04]/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed ${isShining ? 'shine-effect' : ''}`}
      >
        {isFlipping ? 'Flipping...' : 'Flip Coin'}
      </button>
    </div>
  );
}
