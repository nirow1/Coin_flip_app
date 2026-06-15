import { createRoot } from "react-dom/client";
import App from "./App/App.tsx";
import Login from "./App/views/LoginView.tsx";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { GameProvider } from "./Context/GameContext.tsx";
import { AuthProvider } from "./Context/AuthContext.tsx";
import "./styles/index.css";

createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <AuthProvider>
      <GameProvider>
          <Routes>
            <Route path="/" element={<Login />} />
            <Route path="/app" element={<App />} />
          </Routes>
      </GameProvider>
    </AuthProvider>
  </BrowserRouter>
);
  