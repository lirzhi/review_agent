import http from "./http";

export function uploadKnowledge(formData) {
  return http.post("/knowledge/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
}

export function queryKnowledge(params) {
  return http.post("/knowledge/query", params || {});
}

export function semanticQuery(params) {
  return http.post("/knowledge/semantic-query", params || {});
}

export function updateKnowledge(docId, data) {
  return http.post(`/knowledge/${docId}`, data || {});
}

export function deleteKnowledge(docId) {
  return http.post(`/knowledge/${docId}/delete`, {});
}

export function batchDeleteKnowledge(docIds) {
  return http.post("/knowledge/batch-delete", { doc_ids: Array.isArray(docIds) ? docIds : [] });
}

export function parseKnowledge(docId) {
  return http.post(`/knowledge/${docId}/parse`, {});
}
