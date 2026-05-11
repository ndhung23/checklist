import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthProvider";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import Loading from "./components/Loading";

/**
 * PrivateRoute - Wrapper that redirects to login if not authenticated
 */
const PrivateRoute = ({ children }) => {
  const { user, loadingAuth } = useAuth();
  if (loadingAuth) return <Loading />;
  return user ? children : <Navigate to="/login" />;
};

/**
 * AppRoutes - Application routing logic
 * Redirects authenticated users away from login page
 */
function AppRoutes() {
  const { user, loadingAuth } = useAuth();

  if (loadingAuth) return <Loading />;

  return (
    <Routes>
      <Route
        path="/login"
        element={user ? <Navigate to="/dashboard" /> : <LoginPage />}
      />
      <Route
        path="/dashboard"
        element={
          <PrivateRoute>
            <DashboardPage />
          </PrivateRoute>
        }
      />
      <Route
        path="*"
        element={<Navigate to={user ? "/dashboard" : "/login"} />}
      />
    </Routes>
  );
}

/**
 * App - Root component with BrowserRouter and AuthProvider
 */
function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
