# Detailed analysis and migration plan

## 1) What the original `flowkit-image-api` project is doing

### Architecture found in the ZIP

The original project is split into two major parts:

1. A Python FastAPI app under `agent/`
2. A Chrome extension under `extension/`

The FastAPI app exposes `/api/generate`, `/api/edit`, `/health`, and a WebSocket bridge. The extension connects back to the app over WebSocket, captures a Flow bearer token from browser traffic, solves reCAPTCHA via the page context, and sends API responses back through a local callback route.

### Key observations

- `agent/main.py` runs both HTTP and WebSocket servers.
- `agent/api/generate.py` maps prompt + aspect ratio to a Flow image generation call.
- `agent/api/edit.py` downloads a source image, uploads it to Flow, then requests an edit.
- `agent/services/flow_client.py` builds requests for the internal Flow endpoints hosted on `aisandbox-pa.googleapis.com`.
- The extension captures the `Authorization: Bearer ya29...` token by listening to browser requests.
- The extension solves reCAPTCHA by injecting a script into the Flow page and calling `grecaptcha.enterprise.execute(...)`.

### Why it is not directly VPS/Coolify ready

- It assumes the extension is manually loaded into a local browser.
- It assumes the browser session already exists outside Docker.
- There is no bundled browser desktop, VNC, or noVNC layer.
- Persistent session storage is not modeled as container volumes.
- The default local ports are hard-coded for a desktop-style setup.
- The original repo still contains a local SQLite app state/database and extra video-related structures that are unnecessary for an image-only self-hosted service.

## 2) What the `AIStudioToAPI-main` project contributes conceptually

The second ZIP is much more deployable and provides the right structural ideas for self-hosting:

- A Docker-first deployment model
- VNC/noVNC login flow for browser-based account setup
- Explicit healthchecks
- Environment variable driven configuration
- Persistent storage mounts for auth and data
- A web console mindset instead of a local-only script mindset

### Pieces worth borrowing

- Dockerized browser environment
- `x11vnc` + `websockify`/noVNC pattern
- Healthcheck endpoint design
- Compose-based deployment strategy
- README-level operational guidance for self-hosting

### Pieces not worth copying for this Flow-only build

- Multi-account auth-file rotation
- AI Studio chat/proxy layers
- The larger Express/Vue UI surface
- Camoufox-specific account orchestration

For your goal, those are extra moving parts. A persistent Chromium profile is simpler and more natural for Flow.

## 3) Best migration strategy

### Recommended approach

Keep the **FlowKit extension bridge model** from `flowkit-image-api`, but package it into a **single Docker app** that also contains:

- Chromium
- Xvfb
- Fluxbox
- x11vnc
- noVNC/websockify
- FastAPI backend
- Persistent Chromium profile volume

This is the closest functional equivalent to the original FlowKit behavior while removing the need to install a browser or extension separately.

## 4) What changed in this self-hosted build

### Simplified backend

The new backend removes the original local project/database complexity and keeps only the parts needed for:

- extension connection
- image generation
- image editing
- Flow status
- OpenAI-style image endpoint

### Browser/session model

Instead of saving exported auth JSON files like AIStudioToAPI, this build stores the whole Chromium profile in `/data/profile`.

That means:

- first login is manual through noVNC
- later restarts reuse cookies/session automatically
- you do not need a separate auth export/import workflow

### UI model

Instead of building a big management panel, the project exposes:

- a very small landing page
- health JSON
- noVNC endpoint
- API endpoints

That keeps the deployment smaller and easier to maintain.

## 5) Step-by-step migration plan for production

### Phase 1 — Normalize the original FlowKit concept

1. Remove local desktop assumptions.
2. Fix internal ports to container-local values.
3. Keep only image generation and image editing code paths.
4. Bundle the extension into the repo.

### Phase 2 — Containerize the runtime

1. Install Chromium in the image.
2. Install Xvfb, Fluxbox, x11vnc, noVNC, websockify.
3. Launch Chromium with:
   - `--user-data-dir=/data/profile`
   - `--disable-extensions-except=/app/extension`
   - `--load-extension=/app/extension`
4. Open `https://labs.google/fx/tools/flow` on startup.

### Phase 3 — Add persistence

Use Docker volumes for:

- `/data/profile`
- `/data/state`
- `/data/logs`

The important one is `/data/profile`, because that is what preserves the Google login.

### Phase 4 — Add Coolify-ready operations

1. Add `docker-compose.coolify.yml`.
2. Add HTTP healthcheck.
3. Avoid custom Docker networks.
4. Expose app port `4040` and optionally noVNC port `6080`.
5. Keep raw VNC `5900` bound to `127.0.0.1` only.

### Phase 5 — Harden deployment

1. Require `API_KEY`.
2. Require `VNC_PASSWORD`.
3. Limit noVNC exposure to setup periods when possible.
4. Put the API behind HTTPS and, ideally, another auth layer.
5. Treat `/data/profile` as sensitive credential material.

## 6) Coolify deployment checklist

1. Push repository to GitHub.
2. Create a new Coolify resource from the repo.
3. Select Docker Compose build pack.
4. Set compose file to `docker-compose.coolify.yml`.
5. Fill these variables in Coolify:
   - `API_KEY`
   - `VNC_PASSWORD`
   - optional `TZ`
   - optional `FLOW_START_URL`
6. Attach persistent storage by keeping the declared named volumes.
7. Assign domain for `app:4040`.
8. Optionally assign a second domain for `app:6080`.
9. Deploy.
10. Open noVNC, log into Flow once, then use the API.

## 7) Why persistent profile storage is better here than exported auth files

For Flow, a persistent browser profile is the better fit because:

- the extension depends on live browser traffic and page context
- Flow token capture is dynamic
- reCAPTCHA solving happens in-page
- Google can invalidate exported session artifacts more easily than a normal, long-lived profile

So for this use case, the persistent profile approach is cleaner than the AIStudio auth-file approach.

## 8) Security notes you should keep in mind

- Anyone who gets your `/data/profile` volume effectively gets your logged-in browser session.
- noVNC is convenient, but it is still remote browser access. Protect it.
- A VPS in a region unsupported by Flow may still fail even if the software is correct.
- UI selectors and internal API behavior on Flow can change without notice.
- ReCAPTCHA or login challenges may still occasionally require manual re-authentication.

## 9) Alternative designs

### Alternative A — Full Playwright UI automation without extension

Possible, but less attractive here.

Pros:
- No extension needed.

Cons:
- More fragile against Flow UI changes.
- Harder to keep reliable for prompt entry, generation waiting, and result extraction.
- Harder to preserve parity with the original FlowKit approach.

### Alternative B — Separate browser container + API container

Possible, but more operationally complex.

Pros:
- better separation of concerns.

Cons:
- more Coolify setup complexity
- more networking and lifecycle issues
- unnecessary for a single-user VPS deployment

### Recommended choice

For your stated goal, the **single-container bundled-browser architecture** is the best trade-off.

## 10) Result

The included project is GitHub-ready, Dockerized, Coolify-oriented, and focused specifically on Google Flow image generation and editing with:

- VNC/noVNC login
- persistent browser profile storage
- environment-driven configuration
- volumes
- healthchecks
- basic API protection
- OpenAI-style image endpoint
