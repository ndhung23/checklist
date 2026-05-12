document.addEventListener("DOMContentLoaded", () => {
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
});
