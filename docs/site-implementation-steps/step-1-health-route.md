# Step 1 — Health Route

Create the branch and a `/health` route that lives in its own router file.

## 1. Branch

Do all Upmon work on a dedicated branch:

```
git checkout -b access-log
```

## 2. Add the health route

Create a **new file** for health routes and register it with the app. `/health` returns
`200` with a small JSON body:

```json
{ "status": "ok" }
```

Keep it in its own router/controller — not inline in the main application file. Later steps
add more routes alongside it (`/health/agent` for remote log queries,
`/health/frontend-error` for browser error reports), and they all belong in this one file.

Where the file goes depends on the framework:

| Framework | File |
|---|---|
| FastAPI | `routers/health.py` — an `APIRouter`, included from the app factory |
| NestJS | `health/health.controller.ts` — a `@Controller('health')` in a `HealthModule` |
| Laravel | `routes/health.php` — loaded from the route service provider |

The route must be reachable without authentication: Upmon calls it from outside the app.

## 3. Commit

```
git commit -m "health route implementation"
```

---

Next: [step 2 — access log](step-2-access-log.md).
