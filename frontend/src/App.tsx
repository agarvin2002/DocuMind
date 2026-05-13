import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { DocumentsPage } from '@/pages/DocumentsPage'
import { ChatPage } from '@/pages/ChatPage'
import { AnalysisPage } from '@/pages/AnalysisPage'
import { SearchPage } from '@/pages/SearchPage'
import { Toaster } from '@/components/ui/toaster'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<DocumentsPage />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="chat/:documentId" element={<ChatPage />} />
          <Route path="analysis" element={<AnalysisPage />} />
          <Route path="search" element={<SearchPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
      <Toaster />
    </BrowserRouter>
  )
}
