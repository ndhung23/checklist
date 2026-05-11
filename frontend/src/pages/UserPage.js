import React, { useState, useEffect, useCallback } from "react";
import { Button, Modal, Form, Pagination } from "react-bootstrap";
import axiosClient from "../api/axiosClient";
import { useAuth } from "../context/AuthProvider";
import CheckTable from "../components/CheckTable";
import Loading from "../components/Loading";

const ITEMS_PER_PAGE = 10;

/**
 * UserPage - Dashboard for regular users
 * Shows only the authenticated user's checks with CRUD + filters
 */
const UserPage = () => {
  const { user } = useAuth();
  const [checks, setChecks] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [filterDate, setFilterDate] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [searchText, setSearchText] = useState("");

  // Add modal
  const [showAddModal, setShowAddModal] = useState(false);
  const [newCategoryId, setNewCategoryId] = useState("");
  const [newDate, setNewDate] = useState(new Date().toISOString().split("T")[0]);
  const [newStatus, setNewStatus] = useState("x");

  // Delete modal
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);

  /** Fetch user's checks from API */
  const fetchChecks = useCallback(async () => {
    try {
      const res = await axiosClient.get(`/my-checks?userId=${user.id}`);
      setChecks(res.data);
    } catch (err) {
      console.error("Error fetching checks:", err);
    } finally {
      setLoading(false);
    }
  }, [user.id]);

  /** Fetch categories for add modal */
  const fetchCategories = useCallback(async () => {
    try {
      const res = await axiosClient.get("/categories");
      setCategories(res.data);
    } catch (err) {
      console.error("Error fetching categories:", err);
    }
  }, []);

  useEffect(() => {
    fetchChecks();
    fetchCategories();
  }, [fetchChecks, fetchCategories]);

  /** Update check status via PATCH */
  const handleUpdateStatus = async (id, status) => {
    try {
      await axiosClient.patch(`/dailyChecks/${id}`, { status });
      fetchChecks(); // Reload after update
    } catch (err) {
      console.error("Error updating status:", err);
    }
  };

  /** Open delete confirmation modal */
  const handleDeleteClick = (check) => {
    setDeleteTarget(check);
    setShowDeleteModal(true);
  };

  /** Confirm delete */
  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await axiosClient.delete(`/dailyChecks/${deleteTarget.id}`);
      setShowDeleteModal(false);
      setDeleteTarget(null);
      fetchChecks();
    } catch (err) {
      console.error("Error deleting check:", err);
    }
  };

  /** Add new checklist item */
  const handleAddCheck = async (e) => {
    e.preventDefault();
    const category = categories.find((c) => c.id === parseInt(newCategoryId));
    if (!category) return;

    const newCheck = {
      userId: user.id,
      categoryId: category.id,
      symbol: category.symbol,
      category: category.category,
      date: newDate,
      status: newStatus,
      limitTime: category.limitTime,
    };

    try {
      await axiosClient.post("/dailyChecks", newCheck);
      setShowAddModal(false);
      setNewCategoryId("");
      setNewStatus("x");
      fetchChecks();
    } catch (err) {
      console.error("Error adding check:", err);
    }
  };

  /** Apply filters and search */
  const filteredChecks = checks.filter((c) => {
    if (filterDate && c.date !== filterDate) return false;
    if (filterStatus && c.status !== filterStatus) return false;
    if (searchText) {
      const q = searchText.toLowerCase();
      if (
        !c.category.toLowerCase().includes(q) &&
        !c.symbol.toLowerCase().includes(q)
      )
        return false;
    }
    return true;
  });

  // Pagination logic
  const totalPages = Math.ceil(filteredChecks.length / ITEMS_PER_PAGE);
  const paginatedChecks = filteredChecks.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  );

  // Stats
  const stats = {
    total: checks.length,
    completed: checks.filter((c) => c.status === "o").length,
    incomplete: checks.filter((c) => c.status === "x").length,
    abnormal: checks.filter((c) => c.status === "△").length,
  };

  if (loading) return <Loading />;

  return (
    <div className="dashboard-container">
      {/* Header */}
      <div className="dashboard-header">
        <h2>Xin chào, {user.name} 👋</h2>
        <p>Quản lý checklist công việc hằng ngày của bạn</p>
      </div>

      {/* Stat Cards */}
      <div className="stat-cards">
        <div className="stat-card total">
          <div className="stat-value">{stats.total}</div>
          <div className="stat-label">Tổng cộng</div>
        </div>
        <div className="stat-card completed">
          <div className="stat-value">{stats.completed}</div>
          <div className="stat-label">Hoàn thành</div>
        </div>
        <div className="stat-card incomplete">
          <div className="stat-value">{stats.incomplete}</div>
          <div className="stat-label">Chưa xong</div>
        </div>
        <div className="stat-card abnormal">
          <div className="stat-value">{stats.abnormal}</div>
          <div className="stat-label">Bất thường</div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="filter-bar">
        <div style={{ flex: "1", minWidth: "150px" }}>
          <Form.Label>Tìm kiếm</Form.Label>
          <Form.Control
            type="text"
            placeholder="Tìm theo tên hoặc symbol..."
            value={searchText}
            onChange={(e) => { setSearchText(e.target.value); setCurrentPage(1); }}
          />
        </div>
        <div style={{ minWidth: "150px" }}>
          <Form.Label>Ngày</Form.Label>
          <Form.Control
            type="date"
            value={filterDate}
            onChange={(e) => { setFilterDate(e.target.value); setCurrentPage(1); }}
          />
        </div>
        <div style={{ minWidth: "130px" }}>
          <Form.Label>Status</Form.Label>
          <Form.Select
            value={filterStatus}
            onChange={(e) => { setFilterStatus(e.target.value); setCurrentPage(1); }}
          >
            <option value="">Tất cả</option>
            <option value="o">o - Hoàn thành</option>
            <option value="x">x - Chưa xong</option>
            <option value="△">△ - Bất thường</option>
          </Form.Select>
        </div>
        <div>
          <Form.Label>&nbsp;</Form.Label>
          <div className="d-flex gap-2">
            <Button
              className="btn-clear-filter"
              onClick={() => {
                setFilterDate("");
                setFilterStatus("");
                setSearchText("");
                setCurrentPage(1);
              }}
            >
              Xóa lọc
            </Button>
            <Button
              className="btn-add-new"
              onClick={() => setShowAddModal(true)}
            >
              + Thêm mới
            </Button>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="table-card">
        <div className="card-header">
          <h5>📋 Checklist của bạn</h5>
          <span style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
            {filteredChecks.length} mục
          </span>
        </div>
        <CheckTable
          checks={paginatedChecks}
          onUpdateStatus={handleUpdateStatus}
          onDelete={handleDeleteClick}
          showUser={false}
          users={[]}
        />
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="d-flex justify-content-center mt-3">
          <Pagination>
            <Pagination.Prev
              disabled={currentPage === 1}
              onClick={() => setCurrentPage((p) => p - 1)}
            />
            {Array.from({ length: totalPages }, (_, i) => (
              <Pagination.Item
                key={i + 1}
                active={currentPage === i + 1}
                onClick={() => setCurrentPage(i + 1)}
              >
                {i + 1}
              </Pagination.Item>
            ))}
            <Pagination.Next
              disabled={currentPage === totalPages}
              onClick={() => setCurrentPage((p) => p + 1)}
            />
          </Pagination>
        </div>
      )}

      {/* Add Modal */}
      <Modal show={showAddModal} onHide={() => setShowAddModal(false)} centered>
        <Modal.Header closeButton>
          <Modal.Title>Thêm Checklist Mới</Modal.Title>
        </Modal.Header>
        <Form onSubmit={handleAddCheck}>
          <Modal.Body>
            <Form.Group className="mb-3">
              <Form.Label>Hạng mục</Form.Label>
              <Form.Select
                value={newCategoryId}
                onChange={(e) => setNewCategoryId(e.target.value)}
                required
              >
                <option value="">-- Chọn hạng mục --</option>
                {categories.map((cat) => (
                  <option key={cat.id} value={cat.id}>
                    {cat.symbol} - {cat.category}
                  </option>
                ))}
              </Form.Select>
            </Form.Group>
            <Form.Group className="mb-3">
              <Form.Label>Ngày</Form.Label>
              <Form.Control
                type="date"
                value={newDate}
                onChange={(e) => setNewDate(e.target.value)}
                required
              />
            </Form.Group>
            <Form.Group className="mb-3">
              <Form.Label>Trạng thái</Form.Label>
              <Form.Select
                value={newStatus}
                onChange={(e) => setNewStatus(e.target.value)}
              >
                <option value="x">x - Chưa hoàn thành</option>
                <option value="o">o - Hoàn thành</option>
                <option value="△">△ - Bất thường</option>
              </Form.Select>
            </Form.Group>
          </Modal.Body>
          <Modal.Footer>
            <Button variant="secondary" onClick={() => setShowAddModal(false)}>
              Hủy
            </Button>
            <Button type="submit" className="btn-add-new">
              Thêm
            </Button>
          </Modal.Footer>
        </Form>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal show={showDeleteModal} onHide={() => setShowDeleteModal(false)} centered>
        <Modal.Header closeButton>
          <Modal.Title>Xác nhận xóa</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <p className="delete-confirm-text">
            Bạn có chắc muốn xóa checklist{" "}
            <strong>
              {deleteTarget?.symbol} - {deleteTarget?.category}
            </strong>{" "}
            ngày <strong>{deleteTarget?.date}</strong>?
          </p>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowDeleteModal(false)}>
            Hủy
          </Button>
          <Button variant="danger" onClick={handleDeleteConfirm}>
            Xóa
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default UserPage;
