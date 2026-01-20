#!/usr/bin/env python3
"""
Render Deployment Script

This script helps deploy the Screenshot API to Render.com using the Render API.
"""

import os
import sys
import json
import time
import requests

# Configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
RENDER_API_KEY = os.getenv("RENDER_API_KEY")
REPO_OWNER = "medo94my"
REPO_NAME = "screenshot-api"
SERVICE_NAME = "screenshot-api"
PLAN = "starter"  # or "standard" for production

RENDER_API_BASE = "https://api.render.com/v1"
HEADERS = {
    "Authorization": f"Bearer {RENDER_API_KEY}",
    "Content-Type": "application/json",
}


def create_service():
    """Create a new web service on Render."""

    # Get GitHub repository
    repo_url = f"https://github.com/{REPO_OWNER}/{REPO_NAME}"

    service_config = {
        "service": {
            "name": SERVICE_NAME,
            "repo": repo_url,
            "branch": "main",
            "rootDir": "",
            "buildCommand": "pip install -r requirements.txt && playwright install --with-deps chromium",
            "startCommand": "gunicorn -w 2 -k gthread -t 120 -b 0.0.0.0:$PORT app.main:app",
            "env": "python",
            "buildPlan": PLAN,
            "autoDeploy": "yes",
            "notifyOnFail": "default",
            "healthCheckPath": "/health",
        }
    }

    print(f"Creating service '{SERVICE_NAME}' on Render...")
    print(f"Repository: {repo_url}")
    print(f"Plan: {PLAN}")
    print()

    # Note: This is a simplified example. Full implementation would:
    # 1. Get the owner ID from Render API
    # 2. Get the repository ID from GitHub API
    # 3. Create the service via Render API

    print("=" * 60)
    print("DEPLOYMENT INSTRUCTIONS")
    print("=" * 60)
    print()
    print("Since the Render API requires additional setup, here's how to")
    print("deploy using the Render Dashboard:")
    print()
    print("1. Go to: https://dashboard.render.com")
    print("2. Click 'New +' and select 'Web Service'")
    print()
    print("3. Connect your GitHub repository:")
    print(f"   - Repository: {REPO_OWNER}/{REPO_NAME}")
    print("   - Branch: main")
    print()
    print("4. Configure the service:")
    print("   - Name: screenshot-api")
    print("   - Environment: Python 3")
    print("   - Build Command:")
    print(
        "     pip install -r requirements.txt && playwright install --with-deps chromium"
    )
    print("   - Start Command:")
    print("     gunicorn -w 2 -k gthread -t 120 -b 0.0.0.0:$PORT app.main:app")
    print()
    print("5. Set environment variables (optional):")
    print("   - CACHE_TTL_SECONDS: 300")
    print("   - MAX_CONCURRENCY: 2")
    print("   - RATE_LIMIT_PER_MINUTE: 30")
    print("   - MAX_DELAY_MS: 5000")
    print()
    print("6. Health Check:")
    print("   - Path: /health")
    print()
    print("7. Click 'Create Web Service'")
    print()
    print("=" * 60)
    print("Alternative: Deploy using render.yaml blueprint")
    print("=" * 60)
    print()
    print("1. Go to: https://dashboard.render.com/blueprints")
    print("2. Click 'New Blueprint Instance'")
    print("3. Connect your GitHub repository")
    print("4. Render will detect render.yaml and deploy automatically")
    print()
    print("Your service will be available at:")
    print(f"  https://{SERVICE_NAME}-xxxx.onrender.com")
    print()
    print("API Endpoints:")
    print("  - Health: GET /health")
    print("  - Screenshot: GET /screenshot?url=<url>")
    print()
    print("Example usage:")
    print(
        f"  curl https://{SERVICE_NAME}-xxxx.onrender.com/screenshot?url=https://example.com"
    )
    print()


def deploy_docker_image():
    """Deploy using a pre-built Docker image."""

    if not RENDER_API_KEY:
        print("Error: RENDER_API_KEY environment variable not set")
        print("Get your API key from: https://dashboard.render.com/account/api")
        return

    print("Docker deployment via Render API requires:")
    print("1. Build and push Docker image to a registry")
    print("2. Create a 'web' type service with image URL")
    print()
    print("Example commands:")
    print()
    print("# Build and push to Docker Hub")
    print("docker build -t yourusername/screenshot-api:latest .")
    print("docker push yourusername/screenshot-api:latest")
    print()
    print("# Or push to GitHub Container Registry")
    print("docker build -t ghcr.io/medo94my/screenshot-api:latest .")
    print("docker push ghcr.io/medo94my/screenshot-api:latest")
    print()
    print("# Then deploy via Render API or Dashboard")


if __name__ == "__main__":
    print()
    print("=" * 60)
    print("🚀 RENDER DEPLOYMENT - Screenshot API")
    print("=" * 60)
    print()
    print(f"Repository: https://github.com/{REPO_OWNER}/{REPO_NAME}")
    print()

    if len(sys.argv) > 1 and sys.argv[1] == "--docker":
        deploy_docker_image()
    else:
        create_service()
