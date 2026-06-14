  import { createRoot } from "react-dom/client";
  import App from "./App/App.tsx";
  import Login from "./App/views/LoginView.tsx";
  import { BrowserRouter, Routes, Route } from "react-router-dom";
  import { AuthProvider } from "./Context/AuthContext.tsx";
  import "./styles/index.css";

  createRoot(document.getElementById("root")!).render(
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Login />} />
          <Route path="/app" element={<App />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
  