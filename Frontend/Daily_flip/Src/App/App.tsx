import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useContext } from 'react';
import { AuthContext } from '../Context/AuthContext';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import MainView from './views/MainView';
import WalletView from './views/WalletView';
import DepositPage from './views/DepositView';
import WithdrawPage from './views/WithdrawView';
import MyGames from './views/MyGamesView';
import Leaderboards from './views/Leaderboards';
import FriendsPage from './views/FriendsView';

export default function App() {
  const auth = useContext(AuthContext);
  
  if (!auth?.token) {
    return <Navigate to="/" replace />;
  }
  
  const [activeItem, setActiveItem] = useState('main');
  
  return (
    <div className="size-full flex flex-col bg-white">
      <Header />
      <div className="flex-1 flex overflow-hidden">
        <Sidebar activeItem={activeItem} onItemClick={setActiveItem} />
        <main className="flex-1 overflow-auto bg-[#fbf8eb]">
          {activeItem === 'main' && <MainView />}
          {activeItem === 'wallet' && <WalletView onNavigate={setActiveItem} />}
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