import React from "react";
import { Table } from "react-bootstrap";
import StatusBadge from "./StatusBadge";

/**
 * CheckTable - Reusable table for displaying daily checks
 * Props:
 *   checks - array of check items
 *   onUpdateStatus - callback(id, status)
 *   onDelete - callback(check) (admin only)
 *   showUser - show user column (admin/manager)
 *   users - user list for name lookup
 *   nearestId - ID of the nearest-time checklist item
 *   isAdmin - whether current user is admin (controls delete button visibility)
 */
const CheckTable = ({ checks, onUpdateStatus, onDelete, showUser, users, nearestId, isAdmin }) => {
  const getUserName = (userId) => {
    if (!users || users.length === 0) return `User #${userId}`;
    const found = users.find((u) => u.id === userId);
    return found ? found.name : `User #${userId}`;
  };

  if (!checks || checks.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">📭</div>
        <h5>Không có dữ liệu</h5>
        <p>Chưa có checklist nào cho ngày được chọn.</p>
      </div>
    );
  }

  return (
    <div className="table-responsive">
      <Table className="check-table" hover>
        <thead>
          <tr>
            <th>#</th>
            {showUser && <th>Người dùng</th>}
            <th>Symbol</th>
            <th>Category</th>
            <th>Date</th>
            <th>Limit Time</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {checks.map((check, index) => (
            <tr key={check.id} className={check.id === nearestId ? "row-nearest" : ""}>
              <td style={{ color: "#9ca3af", fontWeight: 600 }}>{index + 1}</td>
              {showUser && (
                <td><span className="user-tag">{getUserName(check.userId)}</span></td>
              )}
              <td><span className="symbol-tag">{check.symbol}</span></td>
              <td style={{ fontWeight: 500 }}>
                {check.category}
                {check.id === nearestId && (
                  <span className="nearest-badge">⏰ Gần nhất</span>
                )}
              </td>
              <td><span className="date-text">{check.date}</span></td>
              <td><span className="date-text">{check.limitTime}</span></td>
              <td><StatusBadge status={check.status} /></td>
              <td>
                <div className="action-btn-group">
                  <button className="action-btn btn-complete" title="Hoàn thành (o)"
                    onClick={() => onUpdateStatus(check.id, "o")}>o</button>
                  <button className="action-btn btn-incomplete" title="Chưa hoàn thành (x)"
                    onClick={() => onUpdateStatus(check.id, "x")}>x</button>
                  <button className="action-btn btn-abnormal" title="Bất thường (△)"
                    onClick={() => onUpdateStatus(check.id, "△")}>△</button>
                  {isAdmin && onDelete && (
                    <button className="action-btn btn-delete" title="Xóa"
                      onClick={() => onDelete(check)}>✕</button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
};

export default CheckTable;
