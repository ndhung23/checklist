import React from "react";
import { Badge } from "react-bootstrap";

/**
 * StatusBadge - Displays check status with color-coded badge
 * o = completed (green), x = not completed (secondary), △ = abnormal (warning)
 */
const StatusBadge = ({ status }) => {
  const getConfig = () => {
    switch (status) {
      case "o":
        return { className: "status-badge completed", label: "o" };
      case "x":
        return { className: "status-badge incomplete", label: "x" };
      case "△":
        return { className: "status-badge abnormal", label: "△" };
      default:
        return { className: "status-badge incomplete", label: "—" };
    }
  };

  const config = getConfig();

  return <span className={config.className}>{config.label}</span>;
};

export default StatusBadge;
