import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { ChatMessage } from '@/types'

interface ChatStore {
  conversations: Record<string, ChatMessage[]>
  addMessage: (docId: string, message: ChatMessage) => void
  clearConversation: (docId: string) => void
}

export const useChatStore = create<ChatStore>()(
  persist(
    (set) => ({
      conversations: {},
      addMessage: (docId, message) =>
        set((state) => ({
          conversations: {
            ...state.conversations,
            [docId]: [...(state.conversations[docId] ?? []), message],
          },
        })),
      clearConversation: (docId) =>
        set((state) => ({
          conversations: { ...state.conversations, [docId]: [] },
        })),
    }),
    { name: 'documind-chats' }
  )
)
