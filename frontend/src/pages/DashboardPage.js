import React from "react";
import { useAuth } from "../context/AuthProvider";
import AdminPage from "./AdminPage";
import UserPage from "./UserPage";
import NavbarCustom from "../components/NavbarCustom";
import Loading from "../components/Loading";

/**
 * DashboardPage - Route handler that renders AdminPage or UserPage
 * based on the authenticated user's role
 */
const DashboardPage = () => {
  const { user, loadingAuth } = useAuth();

  if (loadingAuth) return <Loading />;

  return (
    <>
      <NavbarCustom />
      {user.role === "admin" ? <AdminPage /> : <UserPage />}
    </>
  );
};

export default DashboardPage;
