import React, { useState } from "react";
import { Form, Button, Alert, Card } from "react-bootstrap";
import { useAuth } from "../context/AuthProvider";
import { useNavigate } from "react-router-dom";

/**
 * LoginPage - Authentication page with username/password form
 * Uses AuthProvider login() and redirects to dashboard on success
 */
const LoginPage = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await login(username, password);
      navigate("/dashboard");
    } catch (err) {
      const msg =
        err.response?.data?.message || "Đăng nhập thất bại. Vui lòng thử lại.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <div className="login-icon">📋</div>
          <h2>Daily Check</h2>
          <p className="login-subtitle">Đăng nhập để quản lý checklist</p>
        </div>

        {error && (
          <Alert variant="danger" className="mb-3">
            {error}
          </Alert>
        )}

        <Form onSubmit={handleSubmit}>
          <Form.Group className="mb-3" controlId="loginUsername">
            <Form.Label>Username</Form.Label>
            <Form.Control
              type="text"
              placeholder="Nhập tên đăng nhập"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
            />
          </Form.Group>

          <Form.Group className="mb-4" controlId="loginPassword">
            <Form.Label>Password</Form.Label>
            <Form.Control
              type="password"
              placeholder="Nhập mật khẩu"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </Form.Group>

          <Button
            type="submit"
            className="btn-login w-100"
            disabled={loading}
          >
            {loading ? "Đang đăng nhập..." : "Đăng nhập"}
          </Button>
        </Form>

        <div className="login-demo-info">
          <div style={{ marginBottom: "4px", fontWeight: 600, color: "#94a3b8" }}>
            Tài khoản demo:
          </div>
          <div>
            Admin: <code>admin</code> / <code>123456</code>
          </div>
          <div>
            User 1: <code>user1</code> / <code>123456</code>
          </div>
          <div>
            User 2: <code>user2</code> / <code>123456</code>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
