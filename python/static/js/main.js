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
          row.classList.add(payload.result === "o" ? "row-result-o" : "row-result-none");
          const resultCell = row.querySelector("[data-result-cell]");
          if (resultCell) {
            resultCell.innerHTML = payload.result === "o"
              ? '<span class="badge badge-result-o">o</span>'
              : '<span class="badge badge-result-none">Chưa điền</span>';
          }
          const noteCell = row.querySelector("[data-note-cell]");
          if (noteCell) noteCell.textContent = payload.note || "-";
        }
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

  // ===== MODAL BẤT THƯỜNG =====
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

  // ===== THANH THÔNG BÁO CỐ ĐỊNH =====
  const notifBar = document.getElementById("notif-bar");
  const toggleBtn = document.getElementById("notif-toggle-btn");
  const toggleIcon = document.getElementById("notif-toggle-icon");
  const panel = document.getElementById("notif-bar-panel");
  const mainWrapper = document.querySelector(".has-notif-bar");

  if (notifBar && toggleBtn && panel) {
    // Khôi phục trạng thái từ localStorage
    const savedState = localStorage.getItem("notif-bar-open");
    let isOpen = savedState === "true";

    function updatePanelState(animate) {
      if (isOpen) {
        panel.style.display = "block";
        toggleIcon.textContent = "▲";
        document.body.classList.add("notif-panel-open");
        if (mainWrapper) {
          const panelH = panel.offsetHeight;
          mainWrapper.style.paddingTop = (44 + panelH + 20) + "px";
        }
      } else {
        panel.style.display = "none";
        toggleIcon.textContent = "▼";
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

    // Cập nhật padding khi resize
    window.addEventListener("resize", () => {
      if (isOpen) updatePanelState(false);
    });

    // Xử lý nút ẩn từng thông báo (AJAX để không reload trang)
    document.querySelectorAll(".notif-dismiss-form").forEach((dismissForm) => {
      dismissForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const url = dismissForm.action;
        try {
          await fetch(url, { method: "POST", headers: { "X-Requested-With": "XMLHttpRequest" } });
        } catch (_) {}

        // Ẩn item khỏi panel
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
            // Cập nhật số đếm
            const remaining = document.querySelectorAll(".notif-panel-item").length;
            const countBadge = document.querySelector(".notif-bar-count");
            const previewText = document.querySelector(".notif-bar-title-text");
            if (countBadge) countBadge.textContent = remaining;
            if (remaining === 0) {
              // Ẩn toàn bộ thanh thông báo
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
            // Cập nhật padding
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
