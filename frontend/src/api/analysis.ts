import { apiFetch } from './client'
import type { AnalysisJob, WorkflowType } from '@/types'

export interface CreateAnalysisParams {
  question: string
  document_ids: string[]
  workflow_type?: WorkflowType
}

export async function createAnalysisJob(
  params: CreateAnalysisParams
): Promise<AnalysisJob> {
  const res = await apiFetch('/api/v1/analysis/', {
    method: 'POST',
    body: JSON.stringify(params),
  })
  return res.json()
}

export async function getAnalysisJob(id: string): Promise<AnalysisJob> {
  const res = await apiFetch(`/api/v1/analysis/${id}/`)
  return res.json()
}
