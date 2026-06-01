const BASE = "/api";

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || res.statusText);
  }
  return res.json();
}

// Datasets
export const getDatasets = () => req<any[]>("/datasets");
export const createDataset = (body: any) => req("/datasets", { method: "POST", body: JSON.stringify(body) });
export const getDataset = (id: string) => req<any>(`/datasets/${id}`);
export const updateDataset = (id: string, body: any) => req(`/datasets/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const deleteDataset = (id: string) => req(`/datasets/${id}`, { method: "DELETE" });

// Test cases
export const getCases = (datasetId: string, params?: string) =>
  req<any[]>(`/datasets/${datasetId}/cases${params ? "?" + params : ""}`);
export const createCase = (datasetId: string, body: any) =>
  req(`/datasets/${datasetId}/cases`, { method: "POST", body: JSON.stringify(body) });
export const updateCase = (datasetId: string, caseId: string, body: any) =>
  req(`/datasets/${datasetId}/cases/${caseId}`, { method: "PATCH", body: JSON.stringify(body) });
export const deleteCase = (datasetId: string, caseId: string) =>
  req(`/datasets/${datasetId}/cases/${caseId}`, { method: "DELETE" });
export const buildCaseSnapshot = (datasetId: string, caseId: string) =>
  req<any>(`/datasets/${datasetId}/cases/${caseId}/snapshot`, { method: "POST" });
export const backfillSnapshots = (datasetId: string) =>
  req<any>(`/datasets/${datasetId}/snapshots/backfill`, { method: "POST" });

// Task runs
export const getTaskRuns = () => req<any[]>("/tasks");
export const createTaskRun = (body: any) => req("/tasks", { method: "POST", body: JSON.stringify(body) });
export const getTaskRun = (id: string) => req<any>(`/tasks/${id}`);
export const getRunResults = (runId: string) => req<any[]>(`/tasks/${runId}/results`);
export const getRunResult = (runId: string, resultId: string) => req<any>(`/tasks/${runId}/results/${resultId}`);
export const getDiagnosticContext = (runId: string, resultId: string) =>
  req<any>(`/tasks/${runId}/results/${resultId}/diagnostic-context`);
export const createAiAnalysis = (runId: string, resultId: string) =>
  req<any>(`/tasks/${runId}/results/${resultId}/ai-analysis`, { method: "POST" });
export const saveFailureCodes = (runId: string, resultId: string, body: any) =>
  req(`/tasks/${runId}/results/${resultId}/failure-codes`, { method: "POST", body: JSON.stringify(body) });
export const annotate = (runId: string, resultId: string, body: any) =>
  req(`/tasks/${runId}/results/${resultId}/annotate`, { method: "POST", body: JSON.stringify(body) });
export const compareRuns = (ids: string[]) =>
  req<any[]>(`/tasks/analysis/compare?run_ids=${ids.join(",")}`);
export const compareRunsV3 = (ids: string[]) =>
  req<any[]>(`/tasks/analysis/compare-v3?run_ids=${ids.join(",")}`);
export const getCodingBoard = () => req<any[]>("/tasks/analysis/coding-board");
export const getFailureCodes = () => req<any[]>("/tasks/analysis/failure-codes");
export const getFailureTaxonomy = () => req<any[]>("/tasks/analysis/failure-taxonomy");
export const getGraderMeta = () => req<any[]>("/tasks/analysis/grader-meta");
export const createRegressionDataset = (runId: string, body?: any) =>
  req<any>(`/tasks/${runId}/regression-dataset`, { method: "POST", body: JSON.stringify(body || {}) });

// Reports
export const getReports = () => req<any[]>("/reports");
export const getReport = (id: string) => req<any>(`/reports/${id}`);
export const generateReport = (runId: string) => req(`/reports/generate/${runId}`, { method: "POST" });
export const weeklyTrend = () => req<any[]>("/reports/trend/weekly");
