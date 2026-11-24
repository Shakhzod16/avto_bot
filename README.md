# Buxara Avto Magnat · Volkswagen

FastAPI REST API (`/api/v1`), Telegram Mini App (`/app`), administrator panel
(`/admin`) and aiogram 3 bot in one project. The bot is managed by FastAPI's
lifespan; do not start a second polling process. OpenAPI is available at `/docs`.

## Local setup (Windows PowerShell)

Requirements: Python 3.11+, Node.js 20+, npm and a Telegram bot token.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set these values in `.env`:

```dotenv
BOT_TOKEN=your_BotFather_token
ADMIN_IDS=123456789,987654321
JWT_SECRET_KEY=at_least_32_random_bytes
ADMIN_USERNAME=owner
ADMIN_PASSWORD=use_a_long_unique_password
WEBAPP_URL=https://your-public-host/app/
COOKIE_SECURE=false
```

`BOT_TOKEN` and `ADMIN_IDS` are never stored in source code. Create a token with
BotFather and keep it private. A token pasted into a chat or public log should
be revoked and replaced in BotFather. `ADMIN_IDS` contains Telegram numeric IDs,
comma-separated. `WEBAPP_URL` must be a public HTTPS URL for Telegram. The bot
updates its menu button from this value whenever it starts.
`COOKIE_SECURE=false` is only for local HTTP development; use `true` in
production. Use a random `JWT_SECRET_KEY` of at least 32 bytes.

Apply the initial database migration, load the eight catalog cars, create the
first admin, then build both frontends:

```powershell
python -m alembic upgrade head
python -m backend.app.seed
python -m backend.app.cli create-owner
Set-Location frontend\webapp
npm ci
npm run build
Set-Location ..\admin
npm ci
npm run build
Set-Location ..\..
python main.py
```

The seed command is safe to repeat. It inserts or updates the catalog from
`data/cars.json`; it does not add photos or delete extra admin-created trims.
The annual credit rate is intentionally not invented; set it in the owner
panel's **Sozlamalar** page before using the calculator.

The app listens on `http://127.0.0.1:8000`. Health: `/health`, docs: `/docs`,
Mini App: `/app/`, admin: `/admin/`. For frontend hot reload instead of the
production builds, run the API with `python main.py`, then in separate terminals:

```powershell
Set-Location frontend\webapp
npm run dev
```

```powershell
Set-Location frontend\admin
npm run dev
```

Vite proxies `/api` and `/media` to the backend. Dev UI addresses are
`http://localhost:5173` and `http://localhost:5174`.

## Lokal ishlab chiqish (Telegram Mini App uchun HTTPS tunnel)

Telegram Mini App faqat ommaviy HTTPS manzilda ishlaydi; `localhost` va
`127.0.0.1` Telegram ichida ochilmaydi. Backend va build qilingan Mini App
lokalda `http://127.0.0.1:8000` da ishlaydi, cloudflared esa unga HTTPS tunnel
ochadi.

1. [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
   o'rnating (Windows: `winget install --id Cloudflare.cloudflared`) yoki
   [ngrok](https://ngrok.com/download) o'rnating.
2. `.env` faylida `BOT_TOKEN` va `JWT_SECRET_KEY` sozlanganini tekshiring.
   `WEBAPP_URL` hali bo'sh bo'lsa, bot ishga tushadi, ammo Mini App URL haqida
   ogohlantiradi.
3. Loyihaning ildiz papkasidan tunnelni ishga tushiring:

   ```powershell
   .\scripts\dev_tunnel.ps1
   ```

   ```bash
   bash scripts/dev_tunnel.sh
   ```

   Skript cloudflared'ni `http://127.0.0.1:8000` ga ulaydi, vaqtinchalik
   `https://….trycloudflare.com` domenini topadi va `.env` dagi
   `WEBAPP_URL` ni `https://….trycloudflare.com/app/` qilib yangilaydi.
   Tunnel oynasini ochiq qoldiring. Ngrok ishlatsangiz, `ngrok http 8000`
   buyrug'ini bajaring va uning HTTPS forwarding manzilini `.env` dagi
   `WEBAPP_URL=https://….ngrok-free.app/app/` qiymatiga qo'lda yozing.
4. Tunnel URL yaratilgach backendni qayta ishga tushiring (`Ctrl+C`, so'ng
   `python main.py`). Startup botning menyu tugmasini `WEBAPP_URL` bilan
   avtomatik yangilaydi; `/start` buyrug'ini yuborib tekshiring.
5. Tunnel domeni qayta ishga tushganda o'zgarishi mumkin. Tunnelni qayta
   ishga tushirib, backendni ham qayta ishga tushiring. `WEBAPP_URL` HTTPS
   bo'lmasa yoki localhost bo'lsa, bot ishga tushishni davom ettiradi va aniq
   ogohlantirish yozadi, lekin Mini App tugmasini almashtirmaydi.

`initData` backend tomonidan tekshiriladi va qisqa muddatli JWT bilan
almashtiriladi. Faqat bitta backend polling nusxasini ishga tushiring.
Production webhook uchun `BOT_MODE=webhook`, `PUBLIC_BASE_URL` ga ommaviy
HTTPS origin va `WEBHOOK_SECRET` ga 1–256 belgili tasodifiy
`A-Z`, `a-z`, `0-9`, `_` yoki `-` qiymat bering.

## Catalog, prices and photos

- To change prices or vehicle specifications in the initial catalog, edit
  `data/cars.json`, then run `python -m backend.app.seed`. Price values are
  integer so'm; `null` means **Narxi keyinroq e'lon qilinadi**. Prices include
  QQS.
- For ongoing operations, use **Admin → Avtomobillar** to edit cars and trims;
  managers can edit but only an owner can delete cars.
- Upload photos from the car's image manager in the admin panel. JPEG, PNG and
  WebP uploads up to 5 MB are validated and converted to WebP display and
  thumbnail images in `media/cars/`. Set a cover image and reorder images there.
  The admin image manager also associates each file with the selected car, so
  the Mini App can load it from the car's `images` data. To use an existing file,
  open **Admin → Avtomobillar → edit car → images** and upload/select it there;
  copying a file into `media/cars/` alone does not attach it to a car. The
  frontend uses `image_url` when supplied and otherwise uses the associated
  image records; without either, it displays a gradient placeholder. Keep the
  media directory persistent when deploying.

## Docker and HTTPS deployment

Copy `.env.example` to `.env`, set the required secrets and public URLs, then:

```powershell
docker compose up --build -d
docker compose exec backend python -m backend.app.cli create-owner
```

The container applies Alembic migrations and seeds the catalog before starting.
SQLite, uploaded media, logs and backups are persisted in named volumes.
`docker-compose.yml` binds port 8000 to localhost by default. To enable Caddy,
set `DOMAIN` to a DNS name pointing at the server, configure
`WEBAPP_URL=https://your-domain/app/`, `PUBLIC_BASE_URL=https://your-domain`,
and run:

```powershell
docker compose --profile https up --build -d
```

Caddy obtains and renews HTTPS certificates for a real public domain. Set
`WEBAPP_URL=https://your-domain/app/`, `COOKIE_SECURE=true`, restrict
`CORS_ORIGINS` to the deployed origin, and use webhook mode for a multi-instance
deployment. The existing optional `caddy` service/profile is the HTTPS reverse
proxy example; it proxies the app, API and media paths to FastAPI without
changing the default local-only backend port binding. Do not expose the admin
panel or database to the public internet without TLS and operational access
controls.

## Backups

`scripts/backup.py` uses SQLite's online backup API (consistent with a live
database) and adds `media/` to a timestamped ZIP in `BACKUP_DIR`:

```powershell
python -m scripts.backup
docker compose exec backend python -m scripts.backup
```

Schedule it daily with Windows Task Scheduler (run
`python -m scripts.backup` from the project root after activating/installing the
project environment) or a host cron job, for example:

```cron
15 2 * * * cd /path/to/project && docker compose exec -T backend python -m scripts.backup
```

Copy backup archives off the host and periodically verify restoration. A backup
stored only on the same machine is not disaster recovery.

## Validation

```powershell
python -m pytest -q
python -m ruff check .
python -m mypy backend
Set-Location frontend\webapp; npm run lint; npm run typecheck; npm run build
Set-Location ..\admin; npm run lint; npm run typecheck; npm run build
```

## Manual release checklist

### Customer and bot

- `/start` removes any old reply keyboard, upserts the Telegram user and sends
  an inline Mini App button. The menu button opens the HTTPS Mini App; old
  customer button labels point users back to the catalog.
- Home: search, model carousel, SUV/Sedan categories, filter sheet, AWD/FWD,
  engine and price filters, budget entry, sorting and empty results.
- Five bottom tabs: catalog, comparison, credit, favorites and contacts.
- Car detail: photos or placeholder, swipe/gallery, specs, trim prices, null
  price text, favorite toggle, credit and lead actions. Telegram BackButton and
  MainButton should work.
- Compare two or three different cars; remove a car; same car cannot be
  duplicated; highlight differing specifications.
- Credit: choose car and priced trim, test 20–50% down payment and 12–60 months,
  verify the live estimate, approximate-rate label and disclaimer;
  unconfigured rate returns a clear error.
- Request form: test-drive/buy/callback, car/trim selection, name and +998
  phone validation, optional comment, success message and admin notification.
  Invalid or unsigned Telegram `initData` must be rejected.
- Favorites persist for the authenticated Telegram user. Contacts show phone
  links, address, working hours, Instagram, Telegram and optional map.
- Admin notification status buttons update the lead; only configured
  `ADMIN_IDS` can use admin bot commands and callback actions.

### Admin panel

- Owner and manager login; wrong-password lockout; refresh/logout; secure
  production cookies. Manager cannot delete cars, change settings, or access
  owner-only audit/account pages.
- Dashboard counts, status breakdown, top cars, 30-day chart and latest leads.
- Leads filters, paging, search, status updates, internal notes, click-to-call,
  CSV export; confirm phone/name data is correct.
- Cars create/edit, activate/deactivate, trim price including null,
  reorder, image multi-upload, cover, ordering and delete; confirm deleted
  image files are removed.
- Users search and block/unblock; broadcast text/image/button and progress;
  blocked recipients do not stop the send.
- Settings contacts, map, Instagram, working hours, banner and credit rate;
  audit log and manager account creation/deactivation/password reset.
- `/health` is healthy; `/docs` exposes the expected API. Restart the service
  and confirm database, media and logs persist.

## Before going public

- Rotate any bot token that has ever been pasted into a chat, screenshot or
  source file. Keep `.env` out of version control and use strong unique JWT and
  admin credentials.
- Use HTTPS, secure cookies, a strict CORS allowlist, valid Telegram webhook
  secret (if applicable), and only one polling process.
- Create an owner from environment credentials, then remove bootstrap
  credentials from the deployment environment if they are no longer needed.
- Review admin roles and Telegram `ADMIN_IDS`; test unauthorized customer and
  manager requests; verify rate limits and upload size/type checks.
- Verify backups can be restored; monitor rotating logs; update dependencies
  regularly and run tests/lint/type checks before deployment.
