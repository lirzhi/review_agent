import http from "./http";

export function createProject(data) {
  return http.post("/pre-review/projects", data);
}

export function deleteProject(projectId) {
  return http.post(`/pre-review/projects/${projectId}/delete`, {});
}

export function listProjects(params) {
  return http.post("/pre-review/projects/list", params || {});
}

export function projectDetail(projectId) {
  return http.post(`/pre-review/projects/${projectId}/detail`, {});
}

export function uploadSubmission(projectId, formData) {
  return http.post(`/pre-review/projects/${projectId}/submissions/upload`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
}

export function listSubmissions(projectId, params) {
  return http.post(`/pre-review/projects/${projectId}/submissions/list`, params || {});
}

export function submissionContent(projectId, docId) {
  return http.post(`/pre-review/projects/${projectId}/submissions/${docId}/content`, {});
}

export function submissionPreviewUrl(projectId, docId) {
  return `/api/pre-review/projects/${projectId}/submissions/${docId}/preview`;
}

export function dashboardSummary() {
  return http.post("/pre-review/dashboard", {});
}

export function runPreReview(data) {
  return http.post("/pre-review/runs", data);
}

export function runHistory(params) {
  return http.post("/pre-review/runs/history", params || {});
}

export function sectionConclusions(runId, params) {
  return http.post(`/pre-review/runs/${runId}/sections`, params || {});
}

export function sectionTraces(runId, params) {
  return http.post(`/pre-review/runs/${runId}/traces`, params || {});
}

export function exportReport(runId) {
  return http.post(`/pre-review/runs/${runId}/export`);
}

export function addFeedback(runId, data) {
  return http.post(`/pre-review/runs/${runId}/feedback`, data);
}

export function feedbackStats(runId, params) {
  return http.post(`/pre-review/runs/${runId}/feedback/stats`, params || {});
}
