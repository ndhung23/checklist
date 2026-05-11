import React, { createContext, useContext, useState, useEffect } from "react";
import axiosClient from "../api/axiosClient";

const AuthContext = createContext(null);

/** Hook to access auth context */
export const useAuth = () => useContext(AuthContext);

/**
 * AuthProvider - Manages authentication state via Context API
 * Provides: user, login, logout, loadingAuth
 */
export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loadingAuth, setLoadingAuth] = useState(true);

  // Load user from localStorage on mount
  useEffect(() => {
    const storedUser = localStorage.getItem("user");
    if (storedUser) {
      try {
        setUser(JSON.parse(storedUser));
      } catch (e) {
        localStorage.removeItem("user");
      }
    }
    setLoadingAuth(false);
  }, []);

  /** Login - POST /login and store user */
  const login = async (username, password) => {
    const res = await axiosClient.post("/login", { username, password });
    const userData = res.data;
    setUser(userData);
    localStorage.setItem("user", JSON.stringify(userData));
    return userData;
  };

  /** Logout - clear user state and localStorage */
  const logout = () => {
    setUser(null);
    localStorage.removeItem("user");
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, loadingAuth }}>
      {children}
    </AuthContext.Provider>
  );
};
