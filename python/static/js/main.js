document.addEventListener("DOMContentLoaded", () => {
  const adminShell = document.querySelector(".admin-shell");
  const sidebarToggle = document.getElementById("admin-sidebar-toggle");
  if (adminShell && sidebarToggle) {
    const savedSidebarState = localStorage.getItem("admin-sidebar-collapsed");
    if (savedSidebarState === "true") {
      adminShell.classList.add("sidebar-collapsed");
    }
    sidebarToggle.addEventListener("click", () => {
      adminShell.classList.toggle("sidebar-collapsed");
      localStorage.setItem("admin-sidebar-collapsed", adminShell.classList.contains("sidebar-collapsed"));
    });
  }

  document.querySelectorAll(".js-submit-on-change").forEach((control) => {
    control.addEventListener("change", () => control.form?.submit());
  });

  document.querySelectorAll(".js-filter-submit").forEach((filterForm) => {
    let timer = null;
    filterForm.querySelectorAll("select, input[type='date']").forEach((control) => {
      control.addEventListener("change", () => filterForm.requestSubmit());
    });
    filterForm.querySelectorAll("input[type='text']").forEach((control) => {
      control.addEventListener("input", () => {
        window.clearTimeout(timer);
        timer = window.setTimeout(() => filterForm.requestSubmit(), 350);
      });
    });
  });

  document.querySelectorAll(".live-filter").forEach((filterRoot) => {
    const table = document.querySelector(filterRoot.dataset.target || "");
    if (!table) return;
    const selector = `.live-filter[data-target="${filterRoot.dataset.target}"]`;
    const getControls = () => document.querySelectorAll(`${selector} [data-filter]`);
    const applyFilters = () => {
      const controls = Array.from(getControls());
      table.querySelectorAll("tbody tr").forEach((row) => {
        const visible = controls.every((control) => {
          const value = (control.value || "").trim().toLowerCase();
          if (!value) return true;
          const key = control.dataset.filter;
          if (key === "text") return (row.dataset.search || "").toLowerCase().includes(value);
          return (row.dataset[key] || "").toLowerCase() === value;
        });
        row.hidden = !visible;
      });
    };
    getControls().forEach((control) => {
      control.addEventListener(control.tagName === "SELECT" ? "change" : "input", applyFilters);
    });
    document.querySelectorAll(`${selector} [data-filter-clear]`).forEach((button) => {
      button.addEventListener("click", () => {
        getControls().forEach((control) => {
          control.value = "";
        });
        applyFilters();
      });
    });
  });

  const resultClassMap = {
    o: "row-result-o",
    x: "row-result-x",
    "△": "row-result-triangle",
    empty: "row-result-none",
    "": "row-result-none",
  };
  const resultBadgeMap = {
    o: '<span class="badge badge-result-o">o</span>',
    x: '<span class="badge badge-result-x">x</span>',
    "△": '<span class="badge badge-result-triangle">△</span>',
    empty: '<span class="badge badge-result-none">Chưa điền</span>',
    "": '<span class="badge badge-result-none">Chưa điền</span>',
  };

  const ensureEmptyAbnormalRow = (tbody, colspan = 9) => {
    if (tbody.querySelector("[data-report-result-id]")) return;
    tbody.innerHTML = `<tr><td colspan="${colspan}" class="text-center text-muted py-4">Không có báo cáo bất thường.</td></tr>`;
  };

  window.updateAbnormalTableFromPayload = (payload, options = {}) => {
    const tbody = document.getElementById(options.tbodyId || "abnormalReportsBody");
    if (!tbody || !payload || !payload.result_id) return;
    const existing = tbody.querySelector(`tr[data-report-result-id="${payload.result_id}"]`);
    if (!payload.abnormal) {
      if (existing) existing.remove();
      ensureEmptyAbnormalRow(tbody, options.colspan || 9);
      return;
    }

    tbody.querySelectorAll("tr").forEach((row) => {
      if (!row.dataset.reportResultId && row.children.length === 1) row.remove();
    });

    const rowClass = payload.result === "x" ? "row-result-x" : "row-result-triangle";
    const actionHtml = payload.abnormal_url
      ? `<button class="btn btn-sm btn-outline-primary abnormal-trigger" type="button"
            data-bs-toggle="modal" data-bs-target="#abnormalModal"
            data-action="${payload.abnormal_url}"
            data-result="${payload.result}"
            data-id="${payload.result_id}"
            data-symbol="${payload.symbol || ""}"
            data-date="${payload.date || ""}"
            data-content="${payload.content || ""}"
            data-note="${payload.note || payload.content || ""}"
            data-countermeasure=""
            data-confirm-date=""
            data-result-after-fix=""
            data-status="${payload.status || "open"}">Sửa xử lý</button>`
      : "";
    const html = options.compact ? `
      <td>${payload.symbol || ""}</td>
      <td>${payload.date_label || payload.date || ""}</td>
      <td>${payload.note || payload.content || ""}</td>
      <td>-</td>
      <td>-</td>
      <td>-</td>
      <td class="no-print">${actionHtml}</td>` : `

      <td>${existing ? existing.children[0]?.textContent || "" : tbody.querySelectorAll("[data-report-result-id]").length + 1}</td>
      <td>${payload.symbol || ""}</td>
      <td>${payload.date_label || payload.date || ""}</td>
      <td>${payload.note || payload.content || ""}</td>
      <td>-</td>
      <td>-</td>
      <td>-</td>
      <td><span class="badge status-badge status-${payload.status || "open"}">${payload.status || "open"}</span></td>
      <td class="no-print">${actionHtml}</td>`;

    if (existing) {
      existing.className = rowClass;
      existing.innerHTML = html;
      return;
    }
    const tr = document.createElement("tr");
    tr.className = rowClass;
    tr.dataset.reportResultId = payload.result_id;
    tr.innerHTML = html;
    tbody.appendChild(tr);
  };

  document.querySelectorAll(".js-result-btn").forEach((button) => {
    button.addEventListener("click", async () => {
      const formData = new FormData();
      formData.append("result", button.dataset.result || "");
      button.disabled = true;
      try {
        const response = await fetch(button.dataset.url || "", {
          method: "POST",
          body: formData,
          headers: { "X-Requested-With": "XMLHttpRequest" },
        });
        const payload = await response.json();
        if (!response.ok || !payload.ok) throw new Error(payload.message || "Update failed");
        const row = button.closest("tr");
        if (row) {
          row.classList.remove("row-result-o", "row-result-x", "row-result-triangle", "row-result-none");
          row.classList.add(resultClassMap[payload.result] || "row-result-none");
          const resultCell = row.querySelector("[data-result-cell]");
          if (resultCell) {
            resultCell.innerHTML = resultBadgeMap[payload.result] || resultBadgeMap.empty;
          }
          const noteCell = row.querySelector("[data-note-cell]");
          if (noteCell) noteCell.textContent = payload.note || "-";
        }
        window.updateAbnormalTableFromPayload(payload);
      } catch (error) {
        window.alert(error.message);
      } finally {
        button.disabled = false;
      }
    });
  });

  document.querySelectorAll(".leader-note-form input").forEach((input) => {
    let timer = null;
    input.addEventListener("input", () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(async () => {
        const form = input.form;
        if (!form) return;
        try {
          await fetch(form.action, {
            method: "POST",
            body: new FormData(form),
            headers: { "X-Requested-With": "XMLHttpRequest" },
          });
        } catch (_) {}
      }, 500);
    });
  });

  // ===== MODAL Báº¤T THÆ¯á»œNG =====
  const modal = document.getElementById("abnormalModal");
  const form = document.getElementById("abnormalForm");

  if (modal && form) {
    modal.addEventListener("show.bs.modal", (event) => {
      const button = event.relatedTarget;
      if (!button) {
        return;
      }

      form.action = button.dataset.action || "";
      document.getElementById("modalResultId").value = button.dataset.id || "";
      document.getElementById("modalSymbol").value = button.dataset.symbol || "";
      document.getElementById("modalDate").value = button.dataset.date || "";
      document.getElementById("modalResult").value = button.dataset.result || "x";
      document.getElementById("modalContent").value = button.dataset.content || "";
      document.getElementById("modalNote").value = button.dataset.note || "";
      document.getElementById("modalCountermeasure").value = button.dataset.countermeasure || "";
      document.getElementById("modalConfirmDate").value = button.dataset.confirmDate || "";
      document.getElementById("modalResultAfterFix").value = button.dataset.resultAfterFix || "";
      document.getElementById("modalStatus").value = button.dataset.status || "open";
    });
  }

  // ===== THANH THĂ”NG BĂO Cá» Äá»NH =====
  const notifBar = document.getElementById("notif-bar");
  const toggleBtn = document.getElementById("notif-toggle-btn");
  const toggleIcon = document.getElementById("notif-toggle-icon");
  const panel = document.getElementById("notif-bar-panel");
  const mainWrapper = document.querySelector(".has-notif-bar");

  if (notifBar && toggleBtn && panel) {
    // KhĂ´i phá»¥c tráº¡ng thĂ¡i tá»« localStorage
    const savedState = localStorage.getItem("notif-bar-open");
    let isOpen = savedState === "true";

    function updatePanelState(animate) {
      if (isOpen) {
        panel.style.display = "block";
        toggleIcon.innerHTML = '<i class="bi bi-chevron-up"></i>';
        document.body.classList.add("notif-panel-open");
        if (mainWrapper) {
          const panelH = panel.offsetHeight;
          mainWrapper.style.paddingTop = (44 + panelH + 20) + "px";
        }
      } else {
        panel.style.display = "none";
        toggleIcon.innerHTML = '<i class="bi bi-chevron-down"></i>';
        document.body.classList.remove("notif-panel-open");
        if (mainWrapper) {
          mainWrapper.style.paddingTop = "";
        }
      }
    }

    updatePanelState(false);

    toggleBtn.addEventListener("click", () => {
      isOpen = !isOpen;
      localStorage.setItem("notif-bar-open", isOpen);
      updatePanelState(true);
    });

    // Cáº­p nháº­t padding khi resize
    window.addEventListener("resize", () => {
      if (isOpen) updatePanelState(false);
    });

    // Xá»­ lĂ½ nĂºt áº©n tá»«ng thĂ´ng bĂ¡o (AJAX Ä‘á»ƒ khĂ´ng reload trang)
    document.querySelectorAll(".notif-dismiss-form").forEach((dismissForm) => {
      dismissForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const url = dismissForm.action;
        try {
          await fetch(url, { method: "POST", headers: { "X-Requested-With": "XMLHttpRequest" } });
        } catch (_) {}

        // áº¨n item khá»i panel
        const item = dismissForm.closest(".notif-panel-item");
        if (item) {
          item.style.transition = "opacity 0.25s, max-height 0.3s";
          item.style.opacity = "0";
          item.style.overflow = "hidden";
          item.style.maxHeight = item.offsetHeight + "px";
          setTimeout(() => {
            item.style.maxHeight = "0";
            item.style.padding = "0";
            item.style.margin = "0";
          }, 50);
          setTimeout(() => {
            item.remove();
            // Cáº­p nháº­t sá»‘ Ä‘áº¿m
            const remaining = document.querySelectorAll(".notif-panel-item").length;
            const countBadge = document.querySelector(".notif-bar-count");
            const previewText = document.querySelector(".notif-bar-title-text");
            if (countBadge) countBadge.textContent = remaining;
            if (remaining === 0) {
              // áº¨n toĂ n bá»™ thanh thĂ´ng bĂ¡o
              notifBar.style.transition = "opacity 0.4s";
              notifBar.style.opacity = "0";
              setTimeout(() => {
                notifBar.style.display = "none";
                if (mainWrapper) mainWrapper.style.paddingTop = "";
              }, 400);
            } else if (previewText) {
              const firstTitle = document.querySelector(".notif-panel-item-title");
              if (firstTitle) previewText.textContent = firstTitle.textContent;
            }
            // Cáº­p nháº­t padding
            if (isOpen && mainWrapper) {
              const panelH = panel.offsetHeight;
              mainWrapper.style.paddingTop = (44 + panelH + 20) + "px";
            }
          }, 350);
        }
      });
    });
  }
});


