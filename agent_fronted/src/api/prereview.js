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

export function ctdCatalog(projectId) {
  return http.post(`/pre-review/projects/${projectId}/ctd-catalog`, {});
}

export function submissionContent(projectId, docId) {
  return http.post(`/pre-review/projects/${projectId}/submissions/${docId}/content`, {});
}

export function saveSubmissionContent(projectId, docId, data) {
  return http.post(`/pre-review/projects/${projectId}/submissions/${docId}/content/save`, data || {});
}

export function submissionSections(projectId, docId) {
  return http.post(`/pre-review/projects/${projectId}/submissions/${docId}/sections`, {});
}

export function updateSectionConcerns(projectId, sectionId, data) {
  return http.post(`/pre-review/projects/${projectId}/ctd-sections/${sectionId}/concerns`, data || {});
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

export function preReviewStreamUrl(data) {
  const payload = data || {};
  const params = new URLSearchParams();
  params.set("project_id", String(payload.project_id || ""));
  params.set("source_doc_id", String(payload.source_doc_id || ""));
  params.set("run_config", JSON.stringify(payload.run_config || {}));
  return `/api/pre-review/runs/stream?${params.toString()}`;
}

export function runHistory(params) {
  return http.post("/pre-review/runs/history", params || {});
}

export function sectionConclusions(runId, params) {
  return http.post(`/pre-review/runs/${runId}/sections`, params || {});
}

export function sectionOverview(runId) {
  return http.post(`/pre-review/runs/${runId}/sections/overview`, {});
}

export function sectionTraces(runId, params) {
  return http.post(`/pre-review/runs/${runId}/traces`, params || {});
}

export function sectionPatchCandidates(runId, params) {
  return http.post(`/pre-review/runs/${runId}/patches`, params || {});
}

export function replaySection(projectId, docId, sectionId, data) {
  return http.post(
    `/pre-review/projects/${projectId}/submissions/${docId}/sections/${sectionId}/replay`,
    data || {}
  );
}

export function exportReport(runId) {
  return http.post(`/pre-review/runs/${runId}/export`);
}

export function addFeedback(runId, data) {
  return http.post(`/pre-review/runs/${runId}/feedback`, data);
}

export function optimizeFeedback(runId, data) {
  return http.post(`/pre-review/runs/${runId}/feedback/optimize`, data || {});
}

export function feedbackStats(runId, params) {
  return http.post(`/pre-review/runs/${runId}/feedback/stats`, params || {});
}
