import { useCallback, useState } from "react";
import Dashboard from "./components/Dashboard";
import Login from "./components/Login";
import { readToken, saveToken } from "./lib/api";

export default function App() {
  const [token, setToken] = useState(readToken);
  const [username, setUsername] = useState("");

  const handleLogin = (newToken, name) => {
    saveToken(newToken);
    setUsername(name);
    setToken(newToken);
  };

  const handleLogout = useCallback(() => {
    saveToken("");
    setToken("");
  }, []);

  if (!token) return <Login onLogin={handleLogin} />;
  return <Dashboard token={token} username={username} onLogout={handleLogout} />;
}
