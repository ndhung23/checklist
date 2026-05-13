document.addEventListener("DOMContentLoaded", () => {
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
