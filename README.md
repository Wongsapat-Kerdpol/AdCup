# AdCup

Brands post campaigns with a fixed reward budget and a published rate per views. Creators post original
YouTube videos and submit the link. Each video goes through a **system check** and an **admin review**;
once approved it **earns as its views grow**, paid in rounds that share the campaign pool fairly between
all approved videos (minus a flat 10% commission). See `docs/proposal.md` for the full design.

**Stack:** FastAPI · PostgreSQL · Next.js 15 (App Router) + shadcn/ui + Tailwind v4 · Docker Compose

---

## 1. Run it locally

Requirements: **Docker Desktop** (Node.js/Python only needed if you want editor autocomplete).

```bash
cp .env.example .env
docker compose up --build
```

| What | URL |
|---|---|
| Web app | http://localhost:3000 |
| API docs (Swagger) | http://localhost:8000/docs |
| PostgreSQL | `localhost:5432` user/pass/db from `.env` |

Code hot-reloads in both containers. On first start the backend creates tables and seeds demo data.

**Demo accounts** (password `password123`) — or use the one-click *Developer login* on `/login`:

| Role | Email |
|---|---|
| Brand | `brand@adcup.dev`, `brand2@adcup.dev` |
| Creator | `creator@adcup.dev` |
| Admin | `admin@adcup.dev` |

**Changed a model / columns?** Tables are created with `create_all` (no migrations), which never alters
existing tables. Reset your local DB:

```bash
docker compose down -v && docker compose up --build
```

**Added an npm package?** `docker compose exec frontend npm install <pkg>` then
`docker compose up --build frontend` for teammates. Python: add to `backend/requirements.txt` and rebuild.

**Editor autocomplete** (optional): `cd frontend && npm install`, and `pip install -r backend/requirements.txt` in a venv.

---

## 2. Team split — who owns what

| | Owner | Backend | Frontend |
|---|---|---|---|
| **Main** | Wongsapat | `core/*`, `models/*`, `routers/campaigns.py`, `routers/auth.py` (`/me`, `/dev-login`), `seed.py`, `main.py` | layout, header/footer, `/discover`, `CampaignCard`, `middleware.ts` (auth guard), `lib/*`, `components/ui/*` |
| **Person 1** — Auth & Campaign Detail | | `routers/auth.py` (`/register`, `/login`), `routers/campaign_manage.py` | `/login`, `/register`, `/campaigns/[id]`, `/campaigns/new`, `/brand/campaigns` |
| **Person 2** — Submission, Review & Payout | | `routers/submissions.py`, `routers/review.py`, `services/verification.py`, `services/payout.py` | `/submissions`, `/admin/review`, `SubmitContentForm` |
| **Person 3** — YouTube, Wallet, Payment | | `routers/youtube.py`, `services/youtube.py`, `routers/payments.py`, `routers/admin.py` | `/campaigns/[id]/fund`, `/wallet`, `/settings`, `/admin` |

### Submission lifecycle (the core flow)

```
Creator submits YouTube link
      │
      ▼
[pending] ── Round 1: SYSTEM check (Person 2, using Person 3's YouTube data) ──────────────┐
      │   video exists & public · belongs to the creator's connected channel ·            │ fail
      │   published after the campaign started · not a duplicate                         ▼
      │   · views >= campaign.min_views (default 1,000) — waits here until reached   [rejected]
      ▼                                                                          (rejected_by=system)
[under_review] ── Round 2: ADMIN watches the video vs the brand's requirements ───┐
      │            (e.g. "the water bottle must be visible")                      │ reject + reason
      ▼ approve                                                                   ▼
[approved] ── earns INCREMENTALLY on every views refresh                     [rejected]
                                                                          (rejected_by=admin)
```

- **Brands never approve.** They create/fund campaigns and see submissions read-only.
- **Payout rounds** (`services/payout.py`): `new_views = view_count - paid_views` →
  `gross = new_views / 1000 × rate`, limited by **cap per post** and **cap per profile**. If the **remaining
  pool** covers everyone, everyone is paid in full; otherwise it is split **max-min fair**
  (`services/allocation.py`): small earners are paid in full first, the rest share what is left equally.
  Approval order and refresh timing don't matter. 10% commission, net → creator wallet, one `Transaction`
  per video per round. Example at ฿1 / 1K views: round at 1,000 views → +฿1; next round at 3,000 views → +฿2.
- **Who runs a round:** an admin (`POST /api/admin/payout-round`, the "Run payout round" button on `/admin`)
  or `POST /api/youtube/refresh-all`, which refreshes every video first and then runs one round.
  Approving a video or refreshing its views never pays by itself.
- **Views refresh** (Person 3): a "Refresh views" button and/or a periodic job. Pending submissions are
  re-checked (round 1); for approved ones it only stores the new view count.
- **Withdrawal**: the wallet grows with each payout round, cash-out only once balance ≥ ฿1,500.
- **Campaign outlook** (`services/outlook.py`, `GET /api/campaigns/{id}/outlook`, the "Is it still worth
  joining?" card on the campaign page): the pool alone is misleading because approved videos keep gaining views.
  It projects their claims (average views/day so far, capped per post), finds the day the pool runs dry
  (binary search on the answer), and replays the daily payout rounds to estimate what a new video would earn
  (assumes ~2 days until approval, so the backlog is paid first). It is an **estimate**: it ignores cap per
  profile and assumes constant views/day.
- **Demo data for the outlook**: `docker compose exec backend python -m app.demo_queue` adds two demo
  campaigns with videos. It adds users and campaigns — only run it against a throwaway database.
- **Platforms**: YouTube only for now (`SUPPORTED_SUBMISSION_PLATFORMS`); TikTok / IG later.
- **Hand-off between Person 2 & 3**: `services/youtube.py` defines `VideoInfo` + `get_video_info()`.
  Person 2 codes against it now (mock it while Person 3 builds it).

Every placeholder page/router has a `TODO(Person N)` comment listing what to build. Search for your tag:

```bash
git grep "Person 2"
```

### Shared things you should reuse (don't re-create them)

**Backend**
- `from app.core.deps import get_current_user, require_role` — auth guard
  ```python
  @router.post("")
  def create(user: User = Depends(require_role(UserRole.brand)), db: Session = Depends(get_db)): ...
  ```
- `from app.core.security import hash_password, verify_password, create_access_token`
- `from app.core.config import COMMISSION_RATE, MIN_WITHDRAWAL_THB, DEFAULT_MIN_VIEWS, SUPPORTED_SUBMISSION_PLATFORMS`
- `from app.services.payout import split_commission`
- `from app.services.youtube import extract_video_id, get_video_info, VideoInfo`
- Models: `User`, `Campaign`, `Submission`, `Transaction` in `app/models/`. Money is `Decimal`, always **THB**.
  Campaign rate is stored **per 1,000 views** (`rate_per_1k_views`); the UI shows it per 1M.

**Frontend**
- `api<T>(path, { method, body, query })` from `@/lib/api` — adds the JWT automatically, throws `ApiError`.
- `useAuth()` from `@/components/providers/auth-provider` → `{ user, loading, login, logout, refresh }`.
  After your login/register call succeeds: `login(tokenResponse)`.
- `<RequireAuth roles={["brand"]}>` for page content; protected paths are listed in `src/lib/routes.ts`
  (`protectedRoutes`) and enforced by `src/middleware.ts`.
- `routes.*` from `@/lib/routes` — never hard-code paths. Add nav links in `navByRole`.
- `<CampaignCard campaign={c} badge={...} footer={...} />` — `badge` (top-right) for submission status,
  `footer` for buttons.
- `<SubmissionStatusBadge status="under_review" />` from `@/components/campaign/submission-status-badge`.
- Toasts: `import { toast } from "sonner"; toast.success("Campaign created")`.
- shadcn/ui components in `src/components/ui`. Add more with `npx shadcn@latest add <component>`.
- Types in `@/lib/types` mirror the backend schemas — add yours there.

---

## 3. Git workflow

```bash
git checkout -b feature/p2-submissions   # one branch per feature
# ... work, commit often ...
git push -u origin feature/p2-submissions
# open a Pull Request into main, ask one teammate to review
```

- Don't push directly to `main`.
- Only edit files you own; if you need a change in a shared file (models, `lib/*`, `CampaignCard`),
  keep it small and mention it in the PR so the others can pull it early.
- Never commit `.env` or any password / Google secret.

---

## 4. Project structure

```
backend/app/
  core/        config, database, security (JWT/bcrypt), deps (auth guard)
  models/      User, Campaign, Submission, Transaction
  schemas/     Pydantic request/response models
  routers/     one file per feature area (see ownership table)
  services/    business logic (payout engine)
  seed.py      demo data
frontend/src/
  app/         Next.js pages (App Router)
  components/  ui/ (shadcn), layout/, campaign/, discover/, auth/, providers/
  lib/         api client, auth token, routes, types, utils
  middleware.ts  route auth guard
```

## 5. Deploy (later)

The university VM (Ubuntu 24.04, Docker preinstalled) can run the same `docker-compose.yml`.
A production compose (built Next.js, no `--reload`, `DEV_LOGIN_ENABLED=false`) will be added before the demo.
Keep VM credentials out of this repo.
