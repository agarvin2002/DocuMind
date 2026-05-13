import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface ApiKeyStore {
  apiKey: string
  setApiKey: (key: string) => void
}

export const useApiKeyStore = create<ApiKeyStore>()(
  persist(
    (set) => ({
      apiKey: '',
      setApiKey: (key) => set({ apiKey: key }),
    }),
    { name: 'documind-api-key' }
  )
)
