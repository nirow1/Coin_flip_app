---
name: Wire Leaderboards API
overview: Mount the existing FastAPI leaderboard router, fill the empty frontend API client, and replace mock data in Leaderboards.tsx with authenticated fetches for earnings and streak (with a Global/Friends scope toggle).
todos:
  - id: mount-router
    content: Import and include Leader_board router in Backend/main.py
    status: pending
  - id: api-client
    content: Implement types + getEarnings/getStreak in Frontend/src/Api/leaderboard.ts
    status: pending
  - id: wire-view
    content: Replace Leaderboards.tsx mocks with fetch, mapping, loading/error, Global/Friends toggle
    status: pending
  - id: verify
    content: Smoke-test both endpoints and UI while authenticated
    status: pending
isProject: false
---

# Connect Leaderboards to Backend

## Current state

| Layer | Status |
|---|---|
| Backend model/service/schemas/router | Done — [`Backend/Leader_board/`](Backend/Leader_board/) |
| Router mounted in app | **Missing** — [`Backend/main.py`](Backend/main.py) only mounts auth, wallet, game |
| Frontend API wrapper | Empty file — [`Frontend/src/Api/leaderboard.ts`](Frontend/src/Api/leaderboard.ts) |
| UI | Mock arrays only — [`Frontend/src/App/views/Leaderboards.tsx`](Frontend/src/App/views/Leaderboards.tsx) |

Backend already exposes (auth required via `get_current_user`):

- `GET /leaderboard/earnings?friends_only=&limit=` → `{ user_id, username, total_earnings }[]`
- `GET /leaderboard/streak?friends_only=&limit=` → `{ user_id, username, longest_streak }[]`

Stats are updated during cashout/showdown in game flow (`increment_earnings` / `update_streak`); no write endpoints needed for the UI.

```mermaid
sequenceDiagram
  participant UI as Leaderboards.tsx
  participant Api as Api/leaderboard.ts
  participant BE as GET /leaderboard/*
  UI->>Api: getEarnings / getStreak
  Api->>BE: cookie auth + friends_only, limit
  BE-->>UI: ranked rows (order only; no rank field)
```

**Chosen UX default:** keep both boards side-by-side and add a **Global / Friends** toggle that refetches both lists with `friends_only`. No new React context — fetch inside the view (same pattern as one-off screens; wallet/game stay in `GameContext`).

---

## 1. Mount the backend router

In [`Backend/main.py`](Backend/main.py):

```python
from Backend.Leader_board.router import router as leaderboard_router
# ...
app.include_router(leaderboard_router)  # already has prefix="/leaderboard"
```

No schema or service changes required for a basic connect.

---

## 2. Frontend API client

Implement [`Frontend/src/Api/leaderboard.ts`](Frontend/src/Api/leaderboard.ts) mirroring [`Frontend/src/Api/game.ts`](Frontend/src/Api/game.ts):

- Types: `EarningsEntry`, `StreakEntry` matching schema fields.
- Note: `total_earnings` may arrive as a **string** (Pydantic `Decimal` JSON); coerce with `Number(...)` in the view.
- Functions:
  - `getEarningsLeaderboard({ friendsOnly?, limit? })` → `GET /leaderboard/earnings`
  - `getStreakLeaderboard({ friendsOnly?, limit? })` → `GET /leaderboard/streak`
- Use shared [`Frontend/src/Api/client.ts`](Frontend/src/Api/client.ts) (`withCredentials: true`) so JWT cookies work.

Suggested signature:

```ts
export const getEarningsLeaderboard = (friendsOnly = false, limit = 50) =>
  client.get<EarningsEntry[]>('/leaderboard/earnings', {
    params: { friends_only: friendsOnly, limit },
  });
```

---

## 3. Wire [`Leaderboards.tsx`](Frontend/src/App/views/Leaderboards.tsx)

Keep existing layout/styles; replace mock `creditsData` / `streakData`.

1. **State:** `earnings`, `streaks`, `loading`, `error`, `friendsOnly` (boolean).
2. **Fetch on mount + when `friendsOnly` changes:** `Promise.all([getEarningsLeaderboard(...), getStreakLeaderboard(...)])`.
3. **Map API → row shape:**
   - `rank` = index + 1 (backend does not return rank)
   - `name` = `username ?? \`Player ${user_id}\``
   - `avatar` = first letter of display name (current UI pattern)
   - Credits: `Number(total_earnings)` + `toLocaleString()`
   - Streak: `longest_streak`
4. **UI extras (minimal):**
   - Global / Friends toggle near the title
   - Loading placeholder / empty state (“No entries yet”)
   - Error message if fetch fails (401 → user not logged in; endpoints require auth)
5. **Limit:** pass `limit=50` (or 8 if you want to match today’s mock length); boards already scroll naturally in tables.

Do **not** put leaderboard data in `GameContext` unless you later need it on multiple screens.

---

## 4. Auth / empty-data caveats (know before testing)

- Both endpoints require a logged-in user; call only when authenticated (or show “Log in to see leaderboards”).
- `friends_only=true` filters to **friend IDs only** (does not include the current user) — see [`_query_leaderboard`](Backend/Leader_board/service.py) lines 57–65.
- Empty DB → empty arrays until games produce cashouts/streaks (seed script can help: [`Scripts/seed.py`](Scripts/seed.py)).

---

## 5. Verify

1. Restart API; hit `GET /leaderboard/earnings` and `/streak` (logged in) via browser/network or Swagger.
2. Open Leaderboards while logged in — both tables populate; ranks match sort order.
3. Toggle Friends — refetch with `friends_only=true`; empty friends → empty tables.
4. Logged out — graceful error/empty, not a crash.

Optional follow-up (out of scope unless you ask): dedicated pytest for leaderboard routes; highlight the current user’s row.