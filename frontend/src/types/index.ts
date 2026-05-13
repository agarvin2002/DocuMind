export type DocumentStatus = 'pending' | 'processing' | 'ready' | 'failed'

export interface Document {
  id: string
  title: string
  original_filename: string
  file_type: string
  file_size: number
  status: DocumentStatus
  error_message: string | null
  chunk_count: number | null
  created_at: string
  updated_at: string
}

export interface SearchResult {
  chunk_id: string
  document_title: string
  page_number: number
  child_text: string
  parent_text: string
  score: number
}

export interface SearchResponse {
  query: string
  document_id: string
  result_count: number
  results: SearchResult[]
}

export interface Citation {
  chunk_id: string
  document_title: string
  page_number: number
  quote: string
}

export type AnalysisStatus = 'pending' | 'running' | 'complete' | 'failed'
export type WorkflowType = 'simple' | 'multi_hop' | 'comparison' | 'contradiction'

export interface AnalysisResultData {
  workflow_type: WorkflowType
  question: string
  final_answer: string
  sub_questions: string[]
  sub_answers: string[]
  citations: Array<{ document_title: string; page_number: number; chunk_id: string }>
  error: string | null
}

export interface AnalysisJob {
  id: string
  workflow_type: WorkflowType
  status: AnalysisStatus
  input_data: {
    question: string
    document_ids: string[]
    workflow_type: WorkflowType
  }
  result_data: AnalysisResultData | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface HealthResponse {
  status: 'healthy' | 'unhealthy'
  checks: {
    postgres: string
    redis: string
  }
  version: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  isCached?: boolean
  timestamp: string
}
