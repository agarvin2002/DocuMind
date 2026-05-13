import { apiFetch } from './client'
import type { Document } from '@/types'

export async function uploadDocument(
  file: File,
  title?: string
): Promise<Document> {
  const form = new FormData()
  form.append('file', file)
  if (title) form.append('title', title)

  const res = await apiFetch('/api/v1/documents/', {
    method: 'POST',
    body: form,
  })
  return res.json()
}

export async function getDocument(id: string): Promise<Document> {
  const res = await apiFetch(`/api/v1/documents/${id}/`)
  return res.json()
}
