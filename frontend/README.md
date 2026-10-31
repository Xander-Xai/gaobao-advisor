# gaobao-advisor Frontend

Vue 3 SPA for the advisor: chat with structured recommendation cards, public
data explorer, profile/report views, and the administrator workbench.

## Stack

| Technology | Purpose |
|---|---|
| Vue 3 | Components and reactivity |
| Vite | Dev server and production build |
| Pinia | Chat, data-catalog, admin, scene and voice stores |
| Vue Router | `/`, `/data`, `/profile/:id`, `/report/:id`, `/admin` |
| Tailwind CSS | Styling |
| DOMPurify | Markdown/HTML sanitisation |
| Vitest + vue-tsc | Unit tests and TypeScript checks |

## Routes

| Route | View |
|---|---|
| `/` | Chat, structured card, profile side panel |
| `/data` | Data overview, school browser, score trend, plans |
| `/profile/:sessionId` | Persisted profile |
| `/report/:id` | Generated report |
| `/admin` | RBAC operations workbench |

## Data flow

```text
MessageInput -> chat store -> POST /api/v1/chat (SSE)
  -> token / slots / structured / sources / rag_status / degraded / done
  -> incremental message rendering + structured card

DataView -> data store -> GET /api/v1/data/overview|filters|schools|trends
  -> server-side filtering/pagination -> cards, table, SVG trend chart
```

The data explorer never hardcodes counts: every number comes from the backend
catalog response. Trends are rendered per subject type; the chart is an
in-repo SVG component, so no second charting framework is required.

## SSE events

| Event | Purpose |
|---|---|
| `slots` | Extracted profile fields |
| `emotion` | Emotion state used by the response strategy |
| `structured` | Structured recommendation card payload |
| `sources` | RAG citations (`chunk_id`, `source`) |
| `rag_status` | `NO_EVIDENCE` / `RAG_DISABLED` / `RAG_ERROR` |
| `token` | Streamed answer text |
| `degraded` | Explicit fallback notice |
| `done` | Server session ID + HMAC capability token |

## Development

```bash
npm ci
npm run dev       # http://localhost:3080
npm test -- --run # vue-tsc + Vitest
npm run build
```

Vite proxies `/api` and `/ws` to `http://127.0.0.1:8000` in development. To use
a different backend origin, set `VITE_API_BASE_URL` when starting the dev
server.
