import { useQuery } from '@tanstack/react-query'
import { getAnalysisJob } from '@/api/analysis'
import type { AnalysisJob } from '@/types'

export function useAnalysisPolling(jobId: string | null) {
  return useQuery<AnalysisJob>({
    queryKey: ['analysis-job', jobId],
    queryFn: () => getAnalysisJob(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return 3000
      return data.status === 'complete' || data.status === 'failed' ? false : 3000
    },
    staleTime: 0,
  })
}
