# Zoya website

One-page waitlist site for Zoya. Brief: [`docs/website/BRIEF.md`](../docs/website/BRIEF.md).
Next.js (App Router, TypeScript), one global stylesheet (`app/globals.css`), no UI kit.

## Run it

```bash
cd site
npm ci
npm run dev      # http://localhost:3000
npm test         # validators + rate limiter (node's built-in test runner)
npm run lint
npm run build    # passes with no env vars
```

All copy lives in `app/copy.ts`.

## Waitlist and visitor counter

- `lib/waitlist.ts` → `addToWaitlist(email)`. With `DATABASE_URL` set it inserts into Neon Postgres
  (duplicates are success). Without it (local dev only) it appends to `data/waitlist.jsonl` (git-ignored).
  On Vercel a missing `DATABASE_URL` is an error, never a silent file write.
- `lib/visitors.ts` counts unique visitors: the browser stores a random UUID in `localStorage` and
  posts it once to `/api/visit`. The count is server-rendered (revalidated every 60 s) and hidden
  when there is no database.
- Spam: server-side validation and a honeypot field. **No CAPTCHA** (blind audience).
- **Rate limiting is best-effort:** an in-memory per-IP limit per server instance. Serverless
  instances don't share it and it resets on cold start. Use a shared store (e.g. Upstash Redis)
  if abuse shows up.

Tables (created once in Neon):

```sql
create table waitlist (email text primary key, created_at timestamptz not null default now());
create table visitors (id text primary key, first_seen timestamptz not null default now());
```

## The "Hear Zoya" clip

`public/audio/hear-zoya.mp3` is Zoya's real voice: Amazon Polly, voice Kajal, neural, en-IN, ap-south-1.
The word timings in `app/copy.ts` are Polly speech marks for the same text. To regenerate:

```bash
TEXT="I've added eggs, milk and bread. Your total is 243 rupees. Shall I place the order? Say confirm."
aws polly synthesize-speech --profile zoya --region ap-south-1 --engine neural --voice-id Kajal \
  --language-code en-IN --output-format mp3 --sample-rate 24000 --text "$TEXT" public/audio/hear-zoya.mp3
aws polly synthesize-speech --profile zoya --region ap-south-1 --engine neural --voice-id Kajal \
  --language-code en-IN --output-format json --speech-mark-types word --text "$TEXT" marks.jsonl
```

## Deploy (Vercel)

- Import the GitHub repo; set **Root Directory = `site`**. Framework preset: Next.js.
- Environment variables: `DATABASE_URL` (Neon connection string), see `.env.example`.
- Enable Web Analytics on the project. `<Analytics />` renders only when `VERCEL` is set.
- Production builds from `main`.
