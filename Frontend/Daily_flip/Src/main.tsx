  import { createRoot } from "react-dom/client";
  import App from "./App/App.tsx";
  import Login from "./App/views/LoginView.tsx";
  import { AuthProvider } from "./Context/AuthContext.tsx";
  import "./styles/index.css";

  createRoot(document.getElementById("root")!).render(
    <AuthProvider>
      <Login />
    </AuthProvider>
  );
  