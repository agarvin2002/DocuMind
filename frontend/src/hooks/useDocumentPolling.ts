import { useEffect, useMemo } from 'react'
import { getDocument } from '@/api/documents'
import { useDocumentStore } from '@/stores/documentStore'

export function useDocumentPolling() {
  const documents = useDocumentStore((s) => s.documents)
  const updateDocument = useDocumentStore((s) => s.updateDocument)

  const activeIds = useMemo(
    () =>
      documents
        .filter((d) => d.status === 'pending' || d.status === 'processing')
        .map((d) => d.id),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [documents.map((d) => `${d.id}:${d.status}`).join(',')]
  )

  useEffect(() => {
    if (activeIds.length === 0) return

    const poll = async () => {
      for (const id of activeIds) {
        try {
          const updated = await getDocument(id)
          updateDocument(id, updated)
        } catch {
          // silently ignore polling errors
        }
      }
    }

    const interval = setInterval(poll, 2000)
    return () => clearInterval(interval)
  }, [activeIds.join(','), updateDocument])
}
