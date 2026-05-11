/**
 * Helper functions for Daily Check Management System
 */

/** Get today's date as YYYY-MM-DD string */
export const getToday = () => new Date().toISOString().slice(0, 10);

/** Convert "HH:MM" to total minutes */
export function getMinutesFromTime(time) {
  const [hour, minute] = time.split(":").map(Number);
  return hour * 60 + minute;
}

/** Get current time as total minutes */
export function getCurrentMinutes() {
  const now = new Date();
  return now.getHours() * 60 + now.getMinutes();
}

/** Find checklist item nearest to current time */
export function findNearestChecklist(checklists) {
  if (!checklists || checklists.length === 0) return null;
  const current = getCurrentMinutes();
  return checklists.reduce((nearest, item) => {
    const diff = Math.abs(getMinutesFromTime(item.limitTime) - current);
    const nearestDiff = nearest
      ? Math.abs(getMinutesFromTime(nearest.limitTime) - current)
      : Infinity;
    return diff < nearestDiff ? item : nearest;
  }, null);
}

/** Sort checks by date ASC then limitTime ASC */
export function sortByDateAndLimitTime(checks) {
  return [...checks].sort((a, b) => {
    if (a.date !== b.date) return a.date.localeCompare(b.date);
    return a.limitTime.localeCompare(b.limitTime);
  });
}

/** Paginate an array */
export function paginateData(data, currentPage, itemsPerPage) {
  const start = (currentPage - 1) * itemsPerPage;
  return data.slice(start, start + itemsPerPage);
}

/** Format datetime string for display */
export function formatDateTime(isoString) {
  if (!isoString) return "";
  const d = new Date(isoString);
  return d.toLocaleString("vi-VN");
}
