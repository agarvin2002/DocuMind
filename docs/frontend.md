# Frontend

A dark, production-grade React SPA that exposes every DocuMind backend capability through a polished UI.

## Stack

| Layer | Choice |
|-------|--------|
| Framework | React 18 + Vite 5 + TypeScript |
| Styling | Tailwind CSS 3 with custom design tokens |
| Components | Radix UI primitives (Dialog, Accordion, Slider, Checkbox, Tooltip) |
| Data fetching | TanStack Query v5 |
| Routing | React Router v6 |
| State | Zustand with `persist` middleware (localStorage) |
| Streaming | Native `fetch()` + `ReadableStream` — NOT `EventSource` (it's a POST) |
| Icons | Lucide React |
| Fonts | Syne (display), Plus Jakarta Sans (body), JetBrains Mono (code/numbers) |
| E2E tests | Playwright |

## Design Tokens

All tokens are defined in `tailwind.config.ts`:

```
bg-base:        #0a0a0f   page background
bg-surface:     #12121a   cards, panels
bg-elevated:    #1a1a26   modals, dropdowns
bg-border:      #1e1e2e   borders, dividers
accent:         #6366f1   indigo — primary interactive color
accent-hover:   #4f46e5   hover state
txt-primary:    #f1f5f9
txt-secondary:  #94a3b8
txt-muted:      #475569
status-pending:    #f59e0b   amber
status-processing: #3b82f6   blue (+ animate-pulse)
status-ready:      #22c55e   green
status-failed:     #ef4444   red
```

Custom animations: `cursor-blink` (streaming cursor), `shimmer` (skeleton loading), `spin-slow`.

## Directory Structure

```
frontend/
├── index.html                    ← Google Fonts preconnect + load
├── vite.config.ts                ← proxy /api → http://localhost:8000
├── tailwind.config.ts            ← design tokens + custom animations
├── playwright.config.ts          ← webServer auto-start, Chromium only
└── src/
    ├── api/
    │   ├── client.ts             ← apiFetch(): injects X-API-Key, throws ApiError
    │   ├── documents.ts          ← uploadDocument, getDocument
    │   ├── query.ts              ← searchChunks, streamAsk (SSE)
    │   ├── analysis.ts           ← createAnalysisJob, getAnalysisJob
    │   └── health.ts             ← checkHealth
    ├── stores/
    │   ├── apiKeyStore.ts        ← { apiKey, setApiKey } — persisted
    │   ├── documentStore.ts      ← { documents, addDocument, updateDocument } — persisted
    │   ├── chatStore.ts          ← { conversations } keyed by doc ID — persisted
    │   └── toastStore.ts         ← toast queue + toast() helper
    ├── hooks/
    │   ├── useStreamingAsk.ts    ← { ask, answer, citations, isStreaming, isCached, cancel }
    │   ├── useDocumentPolling.ts ← polls pending/processing docs every 2s, stops on terminal
    │   └── useAnalysisPolling.ts ← TanStack Query refetchInterval, stops when complete/failed
    ├── components/
    │   ├── layout/               ← AppLayout, Sidebar, HealthDot
    │   ├── documents/            ← UploadDropzone, DocumentCard, StatusBadge, DocumentGrid
    │   ├── chat/                 ← ChatInterface, MessageBubble, StreamingText, CitationPanel
    │   ├── analysis/             ← AnalysisForm, WorkflowSelector, JobCard, AnalysisResult
    │   ├── search/               ← SearchForm, ChunkResult
    │   └── ui/                   ← Button, Dialog, Accordion, Slider, Checkbox, Toaster
    └── pages/
        ├── DocumentsPage.tsx     ← route: /
        ├── ChatPage.tsx          ← route: /chat/:documentId?
        ├── AnalysisPage.tsx      ← route: /analysis
        └── SearchPage.tsx        ← route: /search
```

## Pages

### Documents (`/`)

The home page. Shows all documents stored in `documentStore` (Zustand + localStorage).

- Drag-and-drop upload zone — accepts PDF only, validates 50MB max before upload
- Stats bar: N documents · M ready · K processing
- Responsive grid of `DocumentCard` components
- Each card shows title, filename, status badge, chunk count (when ready), file size, upload date
- "Ask" button navigates to `/chat/{id}`, "Analyze" navigates to `/analysis?docId={id}`
- `useDocumentPolling` auto-polls any pending/processing documents every 2s

**Empty state:** centered icon + "No documents yet" + "Drop a PDF here" when the store is empty.

### Chat (`/chat/:documentId?`)

Real-time streaming Q&A for a single document.

- Document selector dropdown — shows only `status=ready` documents
- If `:documentId` is in the URL, that document is pre-selected
- Chat history is persisted per document in `chatStore` (Zustand + localStorage)
- `useStreamingAsk` hook manages the SSE connection — tokens accumulate into `answer` state
- After streaming completes, `CitationPanel` shows source chunks with page numbers
- `[1][2]` markers in answer text rendered as indigo superscript badges by `StreamingText`
- "⚡ Cached" badge shown when the first token arrives in < 150ms (semantic cache hit heuristic)
- Cmd+Enter (or ⌘↵) sends the message; Send button disabled while streaming

**Empty state:** if no ready documents exist, "No documents ready" message with link to Documents page.

### Analysis (`/analysis`)

Async LangGraph agent jobs with live status polling.

- Two-column layout: form on the left, job history on the right
- Form: question textarea (2000 char limit), checkbox list of ready documents, `WorkflowSelector`
- `WorkflowSelector`: four radio-style buttons with Radix Tooltip descriptions — Auto-detect (maps to `multi_hop`), Multi-hop, Comparison, Contradiction
- Submitting calls `POST /api/v1/analysis/` and adds a `JobCard` to the history list
- Each `JobCard` calls its own `useAnalysisPolling` hook (necessary because hooks cannot be called in loops)
- Running jobs show a spinner and elapsed time counter
- Completed jobs expand to show `AnalysisResult`: final answer, sub-questions accordion, citations grid
- Job history is session-only — not persisted to localStorage

**Pre-selection:** if `?docId=` query param is present (e.g., from "Analyze" button on a document card), that document is pre-checked in the form.

### Search (`/search`)

Hybrid semantic search debugger — exposes raw retrieval results for inspection.

- Document dropdown (ready docs only), query input, k slider (1–20, default 10)
- Calls `POST /api/v1/query/search/` on submit
- Results rendered as numbered `ChunkResult` cards: rank, score (4 decimal places), page badge, `child_text`
- Each card has a "Show parent context" toggle that expands the full 512-token `parent_text`
- Loading skeletons shown while the request is in flight

## Key Implementation Details

### No document list endpoint

The backend has no `GET /api/v1/documents/` endpoint. `documentStore` (Zustand + `persist`) is the source of truth for the document list. Documents survive page reloads because they're serialized to `localStorage` under the key `documind-documents`.

When you upload a document (`POST /api/v1/documents/`), `uploadDocument()` in `src/api/documents.ts` calls the backend, gets the new `Document` object, and calls `documentStore.addDocument()`. From that point the document is in the store. `useDocumentPolling` polls `GET /api/v1/documents/{id}/` for any document with `status=pending|processing` and calls `updateDocument()` when the status changes.

### SSE streaming

`/api/v1/query/ask/` is a POST endpoint — `EventSource` (browser SSE API) only supports GET. The solution is `fetch()` + `ReadableStream`:

```typescript
const reader = response.body!.getReader()
const decoder = new TextDecoder()
let buffer = ''

while (true) {
  const { done, value } = await reader.read()
  if (done) break
  buffer += decoder.decode(value, { stream: true })
  const blocks = buffer.split('\n\n')
  buffer = blocks.pop() ?? ''

  for (const block of blocks) {
    const eventLine = lines.find(l => l.startsWith('event:'))
    const dataLine = lines.find(l => l.startsWith('data:'))
    const data = dataLine?.slice(6) ?? ''

    if (eventLine?.includes('citations')) callbacks.onCitations(JSON.parse(data))
    else if (eventLine?.includes('done')) { callbacks.onDone(); reader.cancel(); return }
    else if (eventLine?.includes('error')) { callbacks.onError(data); return }
    else if (data && !eventLine) callbacks.onToken(data)
  }
}
```

`useStreamingAsk` wraps this: each `onToken` call appends to `answer` state; `onCitations` sets `citations` state; `onDone` sets `isStreaming = false`. The completed message is persisted to `chatStore` only after `isStreaming` transitions from `true` to `false` — avoiding localStorage thrash on every token.

### Vite proxy

`vite.config.ts` proxies all `/api` requests to `http://localhost:8000`. This means the frontend makes requests to `http://localhost:5173/api/v1/...` which Vite forwards to Django — no CORS configuration required.

## Running

```bash
cd frontend

# Install dependencies (first time)
npm install

# Development server (http://localhost:5173)
npm run dev

# Type-check + production build
npm run build

# Playwright smoke tests
npx playwright test
```

See [docs/testing.md](testing.md) for full details on the Playwright suite.
