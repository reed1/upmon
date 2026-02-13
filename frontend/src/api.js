const BASE_URL = import.meta.env.VITE_API_BASE_URL
const API_KEY = import.meta.env.VITE_API_KEY

export async function fetchStatus(projectId) {
  const url = new URL('/api/v1/status', BASE_URL)
  if (projectId) url.searchParams.set('project_id', projectId)

  const res = await fetch(url, {
    headers: { 'x-api-key': API_KEY },
  })

  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function fetchDailySummary(projectId, days) {
  const url = new URL('/api/v1/daily-summary', BASE_URL)
  if (projectId) url.searchParams.set('project_id', projectId)
  if (days) url.searchParams.set('days', days)

  const res = await fetch(url, {
    headers: { 'x-api-key': API_KEY },
  })

  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}
