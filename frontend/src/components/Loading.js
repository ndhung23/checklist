import React from "react";
import { Spinner } from "react-bootstrap";

/**
 * Loading - Full-page spinner component
 * Displayed while data is being fetched
 */
const Loading = ({ message = "Đang tải dữ liệu..." }) => {
  return (
    <div className="loading-container">
      <Spinner animation="border" role="status" />
      <p>{message}</p>
    </div>
  );
};

export default Loading;
