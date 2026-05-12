# Setup Guide for GitHub Upload

This document walks through uploading the FlowKit Flow Selfhost project to GitHub.

## Prerequisites

- Git installed and configured locally
- GitHub account with push access
- SSH keys configured (or HTTPS) for authentication

## Steps to Upload to GitHub

### 1. Create Repository on GitHub

1. Go to https://github.com/new
2. Enter repository name: `flowkit-flow-coolify`
3. Add description: *"Self-hosted Docker app for Google Flow image generation with built-in Chromium, extension bridge, and REST API"*
4. Choose visibility: **Public** (recommended for open source)
5. ⚠️ **DO NOT** initialize with README (we have our own)
6. ⚠️ **DO NOT** add .gitignore yet (we have one)
7. Click "Create repository"

### 2. On Your Local Machine

```bash
# Navigate to project directory
cd flowkit-flow-coolify

# Initialize git if not already done
git init

# Add remote
git remote add origin https://github.com/YOUR_USERNAME/flowkit-flow-coolify.git
# OR (if using SSH)
git remote add origin git@github.com:YOUR_USERNAME/flowkit-flow-coolify.git

# Verify remote
git remote -v
```

### 3. Initial Commit

```bash
# Check status
git status

# Stage all files
git add .

# Create initial commit
git commit -m "Initial commit: FlowKit Flow Selfhost with Docker support"

# Verify commit
git log --oneline
```

### 4. Push to GitHub

```bash
# Push to main branch
git branch -M main
git push -u origin main

# Verify it worked
git remote show origin
```

### 5. Add GitHub Topics

1. Go to your repository on GitHub
2. Click ⚙️ **Settings** > **General** (left sidebar)
3. Scroll to "Repository topics"
4. Add these topics:
   - `docker`
   - `google-flow`
   - `image-generation`
   - `api`
   - `fastapi`
   - `coolify`
   - `self-hosted`

### 6. Add Branch Protection (Optional but Recommended)

1. Go to **Settings** > **Branches**
2. Click "Add rule"
3. Branch name pattern: `main`
4. Enable:
   - ✅ Require pull request reviews before merging
   - ✅ Require status checks to pass before merging
   - ✅ Require branches to be up to date before merging

## File Structure Summary

Everything needed is included:

```
flowkit-flow-coolify/
├── README.md                  # 📖 Comprehensive usage guide
├── CODE_REVIEW.md            # 📋 Full code review
├── LICENSE                   # 📄 MIT License
├── PROJECT_ANALYSIS.md       # 🏗️ Architecture document
├── Dockerfile                # 🐳 Production Dockerfile
├── docker-compose.yml        # 🔧 Development composition
├── docker-compose.coolify.yml # 🚀 Coolify variant
├── requirements.txt          # 📦 Python dependencies
├── .env.example              # ⚠️ Configuration template
├── .gitignore               # 🚫 Git ignores
├── app/                      # 🐍 FastAPI backend
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── security.py
│   ├── flow_bridge.py
│   └── __init__.py
├── extension/                # 🔌 Chrome extension
│   ├── manifest.json
│   ├── background.js
│   ├── content.js
│   ├── injected.js
│   └── rules.json
├── scripts/                  # 🚀 Startup scripts
│   ├── entrypoint.sh
│   └── launch_chromium.sh
└── static/                   # 🎨 Web dashboard
    └── index.html
```

## Post-Upload Tasks

### 1. Create GitHub Releases

```bash
# Create a git tag for version 0.1.0
git tag -a v0.1.0 -m "Initial release: Docker support, OpenAI API, extension bridge"

# Push tag to GitHub
git push origin v0.1.0
```

Then on GitHub:
1. Go to **Releases** > **Draft a new release**
2. Select tag `v0.1.0`
3. Title: "FlowKit Flow Selfhost v0.1.0"
4. Description:
```markdown
## Features
- Self-contained Docker image with Chromium, Xvfb, x11vnc, noVNC
- Chrome extension bridge for Google Flow token capture
- FastAPI backend with WebSocket support
- OpenAI-compatible image generation endpoint
- Support for Coolify and Docker Compose deployment

## What's New
- Initial public release
- Production-ready with health checks
- Comprehensive documentation
- Security best practices included

## Breaking Changes
- None (initial release)

## Installation
See [README.md](README.md) for setup instructions.
```
5. Click "Publish release"

### 2. Set Up GitHub Pages (Optional)

If you want to host documentation:

1. Go to **Settings** > **Pages**
2. Source: **Deploy from a branch**
3. Branch: **main**, folder: **/docs**
4. Wait for deployment

Or reference the README as primary documentation.

### 3. Add CI/CD with GitHub Actions (Optional)

Create `.github/workflows/docker.yml`:

```yaml
name: Docker Build

on:
  push:
    branches: [main]
    tags: ['v*']

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build Docker image
        run: docker build -t flowkit-flow-coolify .
      
      - name: Scan with Trivy
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'flowkit-flow-coolify:latest'
          format: 'sarif'
          output: 'trivy-results.sarif'
      
      - name: Upload Trivy results
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: 'trivy-results.sarif'
```

## Troubleshooting

### "fatal: not a git repository"

Run in project root:
```bash
cd /path/to/flowkit-flow-coolify
git init
```

### "fatal: remote origin already exists"

Remove and re-add:
```bash
git remote remove origin
git remote add origin https://github.com/YOUR_USERNAME/flowkit-flow-coolify.git
```

### "Permission denied (publickey)"

Use HTTPS instead of SSH:
```bash
git remote set-url origin https://github.com/YOUR_USERNAME/flowkit-flow-coolify.git
```

Or set up SSH keys: https://docs.github.com/en/authentication/connecting-to-github-with-ssh

### "Everything up-to-date"

Make sure you committed:
```bash
git status  # Should be clean
git log     # Should show commits
```

## File Checklist Before Publishing

- ✅ README.md - Complete with examples and troubleshooting
- ✅ CODE_REVIEW.md - Full review results
- ✅ LICENSE - MIT License included
- ✅ .gitignore - Excludes __pycache__, .env, volumes, etc.
- ✅ requirements.txt - All dependencies listed
- ✅ Dockerfile - Production-ready
- ✅ docker-compose.yml - Working configuration
- ✅ .env.example - Configuration template
- ✅ All source code - app/, extension/, scripts/, static/
- ✅ PROJECT_ANALYSIS.md - Architecture documentation

## Keep This Handy

Save your repository URL for future reference:
```
https://github.com/YOUR_USERNAME/flowkit-flow-coolify
```

Push commands for future updates:
```bash
git add .
git commit -m "Your message"
git push origin main
```
