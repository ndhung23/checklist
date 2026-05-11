document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-reset-page='true']").forEach((form) => {
    form.querySelectorAll("input, select").forEach((field) => {
      if (field.name === "page") {
        return;
      }
      field.addEventListener("change", () => {
        const pageField = form.querySelector("input[name='page']");
        if (pageField) {
          pageField.value = "1";
        }
      });
    });
  });
});
