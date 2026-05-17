document.addEventListener("DOMContentLoaded", () => {
  const filterForm = document.getElementById("profile-filter-form");
  const viewInput = document.getElementById("filter-view-mode");
  const excelMonthSelect = document.getElementById("filter-excel-month");

  const btnOpenPw = document.getElementById("btn-open-change-pw");
  const changePwEl = document.getElementById("changePwModal");
  const pwModal = changePwEl ? new bootstrap.Modal(changePwEl) : null;
  if (btnOpenPw && pwModal) {
    btnOpenPw.addEventListener("click", () => pwModal.show());
  }

  const pwNew = document.getElementById("pw-new");
  const pwConfirm = document.getElementById("pw-confirm");
  const pwSubmit = document.getElementById("btn-pw-submit");
  const pwMismatch = document.getElementById("pw-mismatch-msg");
  if (pwConfirm && pwNew) {
    const checkPwMatch = () => {
      if (pwConfirm.value && pwNew.value !== pwConfirm.value) {
        pwConfirm.classList.add("is-invalid");
        if (pwMismatch) pwMismatch.style.display = "block";
        if (pwSubmit) pwSubmit.disabled = true;
      } else {
        pwConfirm.classList.remove("is-invalid");
        if (pwMismatch) pwMismatch.style.display = "none";
        if (pwSubmit) pwSubmit.disabled = false;
      }
    };
    pwNew.addEventListener("input", checkPwMatch);
    pwConfirm.addEventListener("input", checkPwMatch);
  }

  const viewWeekly = document.getElementById("view-weekly");
  const viewDaily = document.getElementById("view-daily");
  const viewExcel = document.getElementById("view-excel");
  const reportTitle = document.getElementById("report-title");
  const reportSubtitle = document.getElementById("report-subtitle");
  const headerActions = document.getElementById("report-header-actions");

  const setVisibleView = (mode) => {
    if (viewWeekly) viewWeekly.style.display = mode === "report" ? "" : "none";
    if (viewDaily) viewDaily.style.display = mode === "daily" ? "" : "none";
    if (viewExcel) viewExcel.style.display = mode === "excel" ? "" : "none";
    if (headerActions) headerActions.style.display = mode === "excel" ? "none" : "";
  };

  const initialMode = filterForm?.dataset.viewMode || "report";
  setVisibleView(initialMode);

  const btnReport = document.getElementById("btn-view-report");
  const btnDaily = document.getElementById("btn-view-daily");
  const btnToggleView = document.getElementById("btn-toggle-view");

  const submitWithView = (mode) => {
    if (!filterForm || !viewInput) return;
    viewInput.value = mode;
    filterForm.submit();
  };

  if (btnReport) {
    btnReport.addEventListener("click", () => submitWithView("report"));
  }
  if (btnDaily) {
    btnDaily.addEventListener("click", () => submitWithView("daily"));
  }
  if (btnToggleView) {
    btnToggleView.addEventListener("click", () => {
      const next = initialMode === "daily" ? "report" : "daily";
      submitWithView(next);
    });
  }

  if (excelMonthSelect) {
    excelMonthSelect.addEventListener("change", () => {
      if (!filterForm || !viewInput) return;
      if (!excelMonthSelect.value) {
        viewInput.value = "report";
        return;
      }
      viewInput.value = "excel";
      filterForm.submit();
    });
  }

  const btnColPicker = document.getElementById("btn-col-picker");
  const colPickerEl = document.getElementById("colPickerModal");
  const colModal = colPickerEl ? new bootstrap.Modal(colPickerEl) : null;
  if (btnColPicker && colModal) {
    btnColPicker.addEventListener("click", () => colModal.show());
  }

  document.querySelectorAll(".col-toggle-cb").forEach((cb) => {
    cb.addEventListener("change", () => {
      const col = cb.dataset.col;
      const visible = cb.checked;
      document.querySelectorAll(`[data-col="${col}"]`).forEach((el) => {
        el.style.display = visible ? "" : "none";
      });
    });
  });

  const btnColAll = document.getElementById("btn-col-all");
  if (btnColAll) {
    btnColAll.addEventListener("click", () => {
      document.querySelectorAll(".col-toggle-cb").forEach((cb) => {
        cb.checked = true;
        const col = cb.dataset.col;
        document.querySelectorAll(`[data-col="${col}"]`).forEach((el) => {
          el.style.display = "";
        });
      });
    });
  }

  const fromInput = document.getElementById("filter-date-from");
  const toInput = document.getElementById("filter-date-to");

  document.querySelectorAll(".quick-range-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const today = new Date();
      const fmt = (d) => d.toISOString().slice(0, 10);
      let start;
      const end = fmt(today);

      if (btn.dataset.range === "week") {
        const day = today.getDay() === 0 ? 6 : today.getDay() - 1;
        const mon = new Date(today);
        mon.setDate(today.getDate() - day);
        start = fmt(mon);
      } else if (btn.dataset.range === "month") {
        start = fmt(new Date(today.getFullYear(), today.getMonth(), 1));
      } else if (btn.dataset.range === "year") {
        start = fmt(new Date(today.getFullYear(), 0, 1));
      }

      if (fromInput) fromInput.value = start;
      if (toInput) toInput.value = end;
      if (viewInput) viewInput.value = "report";
      if (filterForm) filterForm.submit();
    });
  });

  const btnApplyRange = document.getElementById("btn-apply-range");
  if (btnApplyRange) {
    btnApplyRange.addEventListener("click", () => {
      if (viewInput) viewInput.value = initialMode === "excel" ? "report" : initialMode;
      if (filterForm) filterForm.submit();
    });
  }

  if (filterForm && reportTitle) {
    if (initialMode === "excel") {
      reportTitle.textContent = "Checksheet tuần tra nhà máy";
      if (reportSubtitle && excelMonthSelect) {
        const opt = excelMonthSelect.selectedOptions[0];
        reportSubtitle.textContent = opt ? `Tháng ${opt.textContent}` : "";
      }
    } else if (initialMode === "daily") {
      reportTitle.textContent = "Báo cáo theo ngày";
    }
  }

  if (filterForm?.dataset.showPwModal === "1" && pwModal) {
    pwModal.show();
  }
});
