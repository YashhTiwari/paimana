const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

/**
 * Thin fetch wrapper around the FastAPI backend built in STEP 5.
 * Every function here maps 1:1 to a real backend endpoint - nothing
 * in this file invents or hardcodes data.
 */
async function request(path, params = {}) {
  const url = new URL(BASE_URL + path)
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, value)
    }
  })

  let response
  try {
    response = await fetch(url.toString())
  } catch (err) {
    throw new ApiError(
      `Could not reach the backend at ${BASE_URL}. Is the FastAPI server running?`,
      0
    )
  }

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail ?? detail
    } catch {
      // ignore parse errors, fall back to statusText
    }
    // FastAPI validation errors (422) return `detail` as an array of
    // {loc, msg, type} objects rather than a plain string - render a
    // clean, human-readable message instead of a raw JSON dump.
    if (Array.isArray(detail)) {
      detail = detail
        .map((d) => {
          const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : 'input'
          return `${field}: ${d.msg}`
        })
        .join('; ')
    }
    throw new ApiError(
      typeof detail === 'string' ? detail : JSON.stringify(detail),
      response.status
    )
  }

  return response.json()
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

export const api = {
  health: () => request('/api/health'),
  dashboardSummary: () => request('/api/dashboard/summary'),
  listProjects: (params) => request('/api/projects', params),
  getProject: (projectId) => request(`/api/projects/${projectId}`),
  getProjectHistory: (projectId) => request(`/api/projects/${projectId}/history`),
  getProjectRisk: (projectId) => request(`/api/projects/${projectId}/risk`),
  listAlerts: (params) => request('/api/alerts', params),
  topRiskProjects: (limit = 10) => request('/api/top-risk-projects', { limit }),
  listStates: () => request('/api/states'),
  listSectors: () => request('/api/sectors'),
}

export default api
