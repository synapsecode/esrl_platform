# eSRL Frontend (`esrl-app`)

Next.js app for PDF upload, chat, generated notes/summary, video, and game launch controls.

## Development

```bash
npm install
npm run dev
```

## Environment

Set backend base URL:

```bash
NEXT_PUBLIC_API_URI=http://127.0.0.1:5140
```

If omitted, frontend defaults to `http://127.0.0.1:5140` via `lib/api.js`.
You can copy `env.local.example` to `.env.local` and edit as needed.

## Key Routes

- `/` landing page
- `/chat` upload page
- `/chat/[id]` document workspace
- `/how-to-use`
