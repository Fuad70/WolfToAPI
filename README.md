# FlowKit Flow Selfhost

[![Docker](https://img.shields.io/badge/Docker-Compatible-2496ED?logo=docker)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A self-hosted Docker application that packages Google Flow image generation with a built-in Chrome extension bridge, noVNC interface, and REST API. Deploy on any VPS, including through Coolify.

**Use this to generate and edit images using Google's Flow API without needing a local browser or manual setup.**

## 🎯 Features

- **Self-contained**: Chromium browser bundled inside Docker. No manual installation required.
- **Zero-friction login**: noVNC web interface for easy Google account authentication.
- **Session persistence**: Browser profiles and cookies preserved across container restarts.
- **Native bridge**: Custom Chrome extension captures Flow API tokens and calls automatically.
- **Multiple APIs**: 
  - Native JSON endpoints for full control
  - OpenAI-compatible `/v1/images/generations` endpoint for drop-in compatibility
- **Production-ready**: Health checks, logging, error handling, and CORS support.
- **Easy deployment**: Docker Compose or manual setup. Works with Coolify, Portainer, Docker Swarm.

## 📋 Requirements

- Docker (20.10+) or Docker Compose (1.29+)
- 2+ CPU cores recommended
- 2GB RAM minimum (4GB+ recommended)
- 10GB disk space for images and browser cache
- Stable internet connection for Flow API calls

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/yourusername/flowkit-flow-coolify.git
cd flowkit-flow-coolify
```

2. Create `.env` from example:
```bash
cp .env.example .env
```

3. Edit `.env` with your settings:
```env
API_KEY=your-secure-api-key-here
VNC_PASSWORD=your-vnc-password
TZ=UTC
CORS_ORIGINS=*
```

4. Start the container:
```bash
docker-compose up -d
```

5. Wait ~2 minutes for the browser to start, then:
   - Open the homepage: http://localhost:8080
   - Click the built-in **Open noVNC** button
   - Sign into your Google account in the browser session
   - Keep a Flow tab open
   - Check status: http://localhost:8080/health

### Option 2: Docker Run

```bash
docker build -t flowkit-flow-coolify .

docker run -d \
  --name flowkit-flow-coolify \
  -p 8080:8080 \
  -p 6080:6080 \
  -e API_KEY="your-api-key" \
  -e VNC_PASSWORD="your-password" \
  -v flowkit_profile:/data/profile \
  -v flowkit_state:/data/state \
  -v flowkit_logs:/data/logs \
  flowkit-flow-coolify
```

### Option 3: Coolify

1. Create a new application in Coolify
2. Point to this repository
3. Set deployment method to Docker Compose
4. Configure environment variables (API_KEY, VNC_PASSWORD)
5. Deploy

## 📡 API Endpoints

### Health & Status

```bash
GET /health
GET /api/status
```

Returns container health, extension connection status, and Flow token presence.

**Example:**
```bash
curl http://localhost:8080/health
```

**Response:**
```json
{
  "status": "ok",
  "extension_connected": true,
  "flow_key_present": true,
  "details": {
    "uptime_seconds": 3600,
    "profiles_count": 1
  }
}
```

### Generate Images

```bash
POST /api/generate
```

Generate images from a text prompt.

**Headers:**
```
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
```

**Body:**
```json
{
  "prompt": "A cyberpunk neon-lit street scene at night",
  "aspect_ratio": "16:9",
  "image_model": "NANO_BANANA_PRO"
}
```

**Aspect ratios:**
- `1:1` (square)
- `16:9` (landscape)
- `9:16` (portrait)
- `4:3` (standard)
- `3:4` (standard portrait)

**Image models:**
- `NANO_BANANA_PRO` (default, fastest)
- `NANO_BANANA_2` (quality mode)

**Response:**
```json
{
  "url": "https://lh3.google.com/...",
  "raw": { ... full response from Flow API ... }
}
```

### Edit Images

```bash
POST /api/edit
```

Edit existing images using Flow's editing capabilities.

**Headers:**
```
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
```

**Body:**
```json
{
  "image_url": "https://example.com/image.jpg",
  "prompt": "Make it more vibrant and add sunset colors",
  "aspect_ratio": "16:9",
  "image_model": "NANO_BANANA_PRO"
}
```

**Response:**
```json
{
  "url": "https://lh3.google.com/...",
  "raw": { ... }
}
```

### OpenAI Compatible Endpoint

```bash
POST /v1/images/generations
```

Drop-in compatible with OpenAI's image generation API.

**Headers:**
```
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
```

**Body:**
```json
{
  "prompt": "A serene mountain landscape at sunrise",
  "model": "flow-nano-banana-pro",
  "size": "1536x1024",
  "n": 1,
  "response_format": "url"
}
```

**Supported sizes:**
- `1024x1024`
- `1536x1024` (default)
- `1024x1536`
- `1600x900`
- `900x1600`
- `1280x768`

**Response:**
```json
{
  "created": 1234567890,
  "data": [
    {
      "url": "https://lh3.google.com/..."
    }
  ]
}
```

### Open Flow in Browser

```bash
POST /api/browser/open-flow
```

Programmatically open the Flow interface in the bundled browser.

**Headers:**
```
Authorization: Bearer YOUR_API_KEY
```

**Response:**
```json
{
  "ok": true,
  "result": { ... }
}
```

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `API_KEY` | `change-me` | ✅ Yes | API authentication key for all POST endpoints |
| `VNC_PASSWORD` | `change-me-too` | ✅ Yes | Password for VNC/noVNC access |
| `TZ` | `UTC` | ❌ No | Timezone (e.g., `America/New_York`, `Europe/London`) |
| `FLOW_START_URL` | `https://labs.google/fx/tools/flow` | ❌ No | Flow interface URL |
| `SCREEN_WIDTH` | `1600` | ❌ No | Virtual desktop width in pixels |
| `SCREEN_HEIGHT` | `900` | ❌ No | Virtual desktop height in pixels |
| `CORS_ORIGINS` | `*` | ❌ No | Comma-separated CORS origins |
| `LOG_LEVEL` | `INFO` | ❌ No | Log level (DEBUG, INFO, WARNING, ERROR) |
| `BROWSER_PROFILE_DIR` | `/data/profile` | ❌ No | Chromium profile directory |
| `STATE_DIR` | `/data/state` | ❌ No | Application state directory |
| `LOG_DIR` | `/data/logs` | ❌ No | Application logs directory |

### Persistent Volumes

| Volume | Purpose |
|--------|---------|
| `/data/profile` | Chromium browser profile (cookies, local storage, extensions) |
| `/data/state` | Application state files |
| `/data/logs` | Application logs |

Bind these to named volumes or host directories for persistence.

## 🔒 Security Considerations

1. **API Key**: Use a strong, randomly generated API key:
   ```bash
   openssl rand -base64 32
   ```

2. **VNC Password**: Use a strong password. Change from default immediately.

3. **Network Access**:
   - HTTP (8080): Keep on private network or behind HTTPS proxy
   - noVNC (6080): Keep on private network or VPN-protected
   - VNC (5900): Only expose if necessary, restrict to localhost

4. **CORS**: Restrict `CORS_ORIGINS` to known domains in production:
   ```
   CORS_ORIGINS=https://app.example.com,https://api.example.com
   ```

5. **Logs**: Monitor logs for errors or suspicious activity:
   ```bash
   docker logs -f flowkit-flow-coolify
   ```

## 📝 Usage Examples

### Python

```python
import requests

API_KEY = "your-api-key"
BASE_URL = "http://localhost:8080"

def generate_image(prompt):
    response = requests.post(
        f"{BASE_URL}/api/generate",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "prompt": prompt,
            "aspect_ratio": "16:9",
            "image_model": "NANO_BANANA_PRO"
        }
    )
    return response.json()["url"]

# Generate image
url = generate_image("A futuristic city with flying cars")
print(f"Generated: {url}")
```

### JavaScript/Node.js

```javascript
const API_KEY = "your-api-key";
const BASE_URL = "http://localhost:8080";

async function generateImage(prompt) {
  const response = await fetch(`${BASE_URL}/api/generate`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${API_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      prompt: prompt,
      aspect_ratio: "16:9"
    })
  });
  
  const data = await response.json();
  return data.url;
}

// Generate image
const url = await generateImage("A serene forest at dawn");
console.log("Generated:", url);
```

### cURL

```bash
# Generate
curl -X POST http://localhost:8080/api/generate \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A minimalist design of a coffee cup",
    "aspect_ratio": "1:1"
  }'

# Edit
curl -X POST http://localhost:8080/api/edit \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/image.jpg",
    "prompt": "Add sunset colors",
    "aspect_ratio": "16:9"
  }'

# OpenAI compatible
curl -X POST http://localhost:8080/v1/images/generations \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A dog wearing glasses",
    "model": "flow-nano-banana-pro",
    "size": "1024x1024"
  }'
```

## 🔧 Development

### Local Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/flowkit-flow-coolify.git
cd flowkit-flow-coolify
```

2. Create Python virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env`:
```bash
cp .env.example .env
```

5. Run locally (requires Docker for the browser):
```bash
docker-compose up
```

### Project Structure

```
.
├── app/                          # FastAPI application
│   ├── main.py                   # Main endpoints
│   ├── config.py                 # Configuration from environment
│   ├── models.py                 # Pydantic request/response models
│   ├── security.py               # API key validation
│   ├── flow_bridge.py            # Extension ↔ Flow API bridge
│   └── __init__.py
├── extension/                    # Chrome extension
│   ├── manifest.json             # Extension manifest
│   ├── background.js             # Service worker
│   ├── content.js                # Content script
│   ├── injected.js               # Page-context script (reCAPTCHA)
│   └── rules.json                # Request header rules
├── scripts/
│   ├── entrypoint.sh             # Container startup script
│   └── launch_chromium.sh        # Browser launcher
├── static/
│   └── index.html                # Web dashboard
├── Dockerfile                    # Container image definition
├── docker-compose.yml            # Compose setup for localhost
├── docker-compose.coolify.yml    # Coolify-specific setup
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

### Building the Docker Image

```bash
# Standard build
docker build -t flowkit-flow-coolify .

# Build with buildkit (faster)
DOCKER_BUILDKIT=1 docker build -t flowkit-flow-coolify .
```

### Code Style

The project uses:
- Python 3.12+
- FastAPI with async/await
- Standard library modules where possible
- Type hints for clarity

## 🐛 Troubleshooting

### "Extension not connected yet"

**Problem**: API returns 503 error about extension not connected.

**Solution**:
1. Open noVNC (http://localhost:6080)
2. Wait for desktop to load (5-10 seconds)
3. Check if Chromium is running (should open automatically)
4. Keep a Flow tab open
5. Check `/data/logs/browser-launcher.log` for Chrome startup errors

### "Flow key not present"

**Problem**: Health check shows `flow_key_present: false`.

**Solution**:
1. Open noVNC and navigate to https://labs.google/fx/tools/flow
2. Sign in with your Google account
3. Keep the tab open (extension listens for the auth token)
4. Wait 10-15 seconds for token capture
5. Check health endpoint again

### "No image URL found in response"

**Problem**: Generation succeeds but response parsing fails.

**Solution**:
1. Check Flow API hasn't changed (see Project Analysis)
2. Review `/data/logs/app.log` for full response
3. Verify Flow tab is still open and user still authenticated
4. Try regenerating a few times (rate limiting)

### Container won't start

**Problem**: `docker logs` shows errors.

**Solutions**:
- Check `.env` file exists and has `API_KEY` and `VNC_PASSWORD`
- Increase startup timeout (healthcheck start_period to 120s)
- Check disk space: `df -h`
- Check memory: `free -h` (need at least 2GB)
- Rebuild: `docker-compose down && docker-compose up --build`

### High memory usage

**Problem**: Container using 1GB+ RAM.

**Solutions**:
- Reduce `SCREEN_WIDTH`/`SCREEN_HEIGHT`
- Chromium and Xvfb are resource-intensive
- Use a VPS with 4GB+ RAM for production

### API key not working

**Problem**: 401 Unauthorized on API requests.

**Solutions**:
- Double-check `API_KEY` in `.env` file
- Verify header format: `Authorization: Bearer YOUR_KEY`
- Alternative header: `X-API-Key: YOUR_KEY`
- Restart container after changing `.env`: `docker-compose restart`

## 📊 Monitoring

### Health Checks

The service includes automatic Docker health checks. View status:
```bash
docker ps  # Shows health status column
```

### Logs

View logs in real-time:
```bash
docker logs -f flowkit-flow-coolify
```

View specific component logs:
```bash
docker exec flowkit-flow-coolify tail -f /data/logs/app.log
docker exec flowkit-flow-coolify tail -f /data/logs/browser-launcher.log
docker exec flowkit-flow-coolify tail -f /data/logs/x11vnc.log
```

### Performance Metrics

```bash
docker stats flowkit-flow-coolify
```

## 🤝 Contributing

Contributions welcome! Areas of interest:
- Performance optimizations
- Additional image models
- UI improvements
- Documentation
- Bug fixes

## 📄 License

MIT License - See LICENSE file for details

## ⚠️ Disclaimer

This project is for authorized use only. Ensure you have:
- ✅ A valid Google account
- ✅ Access to Google Flow API
- ✅ Compliance with Google's Terms of Service
- ✅ Proper API credentials (not hardcoded in code)

Unauthorized use or redistribution of generated content may violate terms of service.

## 🔗 Related Projects

- [Original FlowKit Image API](https://github.com/yourusername/flowkit-image-api)
- [Google Flow Labs](https://labs.google/fx/tools/flow)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

## 📞 Support

- **Issues**: Open GitHub issues for bugs and feature requests
- **Discussions**: Use GitHub Discussions for questions
- **Documentation**: See PROJECT_ANALYSIS.md for architecture details

---

**Made with ❤️ for the open source community**
- `/data/state` – VNC password file and future state files.
- `/data/logs` – app, VNC, Xvfb, and Chromium logs.

## Local Docker Compose

```bash
cp .env.example .env
# edit .env

docker compose up -d --build
```

Then open:

- App: `http://YOUR_HOST:8080`
- noVNC: `http://YOUR_HOST:6080/vnc.html?autoconnect=1&resize=remote`

## Coolify deployment

### Option A: Docker Compose build pack

1. Push this repository to GitHub.
2. In Coolify, create a new resource from that repo.
3. Choose **Docker Compose** build pack.
4. Use base directory `/`.
5. Set compose file to `docker-compose.coolify.yml`.
6. Fill `API_KEY` and `VNC_PASSWORD` in the Coolify environment UI.
7. Assign one domain to `app:8080` for the API and dashboard.
8. Assign a second domain to `app:6080` for noVNC if you want browser-based login over the web.
9. Deploy.

### Option B: Build image then deploy in Coolify

1. Build and publish the image from this repo.
2. In Coolify choose a Docker image deployment.
3. Expose ports `8080` and optionally `6080`.
4. Attach persistent volumes for `/data/profile`, `/data/state`, and `/data/logs`.
5. Set `API_KEY` and `VNC_PASSWORD`.

## First login flow

1. Open the noVNC page.
2. Log in to Google.
3. Open or keep a Flow tab open.
4. Wait until `/health` shows both `extension_connected=true` and `flow_key_present=true`.
5. Send cURL requests.

## Example cURL

```bash
curl -X POST http://YOUR_HOST:8080/v1/images/generations \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A cinematic perfume bottle on wet black stone, dramatic rim light",
    "model": "flow-nano-banana-pro",
    "size": "1536x1024"
  }'
```

## Healthcheck

The image exposes `GET /health`, and both the Dockerfile and compose files include an HTTP healthcheck against that endpoint.

## Security notes

- Use a strong `API_KEY` and `VNC_PASSWORD`.
- Prefer exposing `6080` only during the login/setup phase.
- Keep raw VNC port `5900` bound to localhost only.
- Persistent browser profiles contain live Google session data, so protect the volume and your Coolify project carefully.
- This build uses browser automation against a third-party web app. Flow UI/API changes can break it.
- The Google Flow frontend key used here is a browser-facing key taken from the original project pattern and may rotate in the future.
- If you want stronger isolation, place the app behind Cloudflare Access, Authelia, or another identity-aware proxy.

## Limits and assumptions

- This build is focused on **Flow image generation/editing only**.
- It does not include the larger multi-account and auth-file management stack from AIStudioToAPI.
- It assumes the Google account can use Flow in the region where the VPS/browser runs.
- The first login still requires manual interaction through noVNC.

## Suggested next improvements

- Add a small admin page with browser restart and screenshot endpoints.
- Add optional basic auth in front of the web dashboard.
- Add request queueing and retries.
- Add response download mirroring to object storage if you need durable output links.
