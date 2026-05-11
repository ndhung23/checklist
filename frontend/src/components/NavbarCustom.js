import React from "react";
import { Navbar, Nav, Container, Button } from "react-bootstrap";
import { useAuth } from "../context/AuthProvider";
import { useNavigate } from "react-router-dom";

/**
 * NavbarCustom - Top navigation bar
 * Shows brand, user info, notification/print/logout buttons
 */
const NavbarCustom = ({ onNotifyClick, notifyCount, onPrintClick }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  if (!user) return null;

  return (
    <Navbar expand="lg" className="navbar-custom no-print" sticky="top">
      <Container fluid className="px-4">
        <Navbar.Brand href="#">📋 Daily Check</Navbar.Brand>
        <Navbar.Toggle aria-controls="main-navbar" />
        <Navbar.Collapse id="main-navbar" className="justify-content-end">
          <Nav className="align-items-center flex-wrap gap-2">
            {/* Print button */}
            {onPrintClick && (
              <Button className="btn-print" size="sm" onClick={onPrintClick}>
                🖨️ In checklist
              </Button>
            )}
            {/* Notification button */}
            {onNotifyClick && (
              <Button className="btn-notify" size="sm" onClick={onNotifyClick}>
                🔔 Thông báo
                {notifyCount > 0 && (
                  <span className="notify-count">{notifyCount}</span>
                )}
              </Button>
            )}
            {/* User badge */}
            <span className="navbar-user-badge">
              <span className={`role-dot ${user.role}`}></span>
              <span>{user.name}</span>
              <span style={{ color: "#9ca3af", fontSize: "0.72rem" }}>
                ({user.role})
              </span>
            </span>
            <Button className="btn-logout" size="sm" onClick={handleLogout}>
              Đăng xuất
            </Button>
          </Nav>
        </Navbar.Collapse>
      </Container>
    </Navbar>
  );
};

export default NavbarCustom;
