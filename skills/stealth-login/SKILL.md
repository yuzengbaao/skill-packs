---
name: stealth-login
description: "Anti-detection browser login for Discord and X (Twitter) using Playwright + playwright-stealth + GLM-5 Vision CAPTCHA solving."
metadata:
  openclaw:
    emoji: "\U0001F512"
    requires:
      bins: [python3]
      env: [ANTHROPIC_AUTH_TOKEN, ANTHROPIC_BASE_URL]
      python: ">=3.12"
    setup: |
      source /root/.browser-use-venv/bin/activate
      pip install playwright playwright-stealth httpx
      playwright install chromium
---

# Stealth Login Skill

Anti-detection browser login for Discord and X (Twitter). Uses playwright-stealth for evasion, GLM-5 Vision API for CAPTCHA solving, and session persistence to avoid repeated logins.

## Environment

```bash
source /root/.browser-use-venv/bin/activate
```

### Credentials

Set environment variables or create `/root/.openclaw/workspace/auth/credentials.json`:

```json
{
  "discord": {"email": "...", "password": "..."},
  "twitter": {"username": "...", "email": "...", "password": "...", "phone": "..."}
}
```

## Quick Usage

### Discord Login

```python
import asyncio, sys
sys.path.insert(0, '/root/.openclaw/workspace/skills/stealth-login')
from stealth_login import StealthLoginConfig, DiscordLogin

async def main():
    config = StealthLoginConfig.load()
    login = DiscordLogin(config)
    result = await login.login()
    print(f"Success: {result.success}, Error: {result.error}")

asyncio.run(main())
```

### X (Twitter) Login

```python
from stealth_login import StealthLoginConfig, TwitterLogin

async def main():
    config = StealthLoginConfig.load()
    login = TwitterLogin(config)
    result = await login.login()
    print(f"Success: {result.success}, Phone required: {result.requires_phone}")

asyncio.run(main())
```

## API Reference

### StealthLoginConfig

| Parameter | Default | Description |
|-----------|---------|-------------|
| `headless` | True | Run browser headless |
| `max_captcha_retries` | 3 | CAPTCHA solve attempts |
| `session_max_age_hours` | 24 | Session expiry in hours |

### LoginResult

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Login succeeded |
| `service` | str | "discord" or "twitter" |
| `requires_mfa` | bool | MFA code needed |
| `requires_phone` | bool | Phone verification needed |
| `error` | str? | Error message |
| `state_saved` | bool | Session persisted |

### HcaptchaSolver / ArkoseSolver

| Method | Description |
|--------|-------------|
| `solve()` | Attempt to solve CAPTCHA |
| `detect()` | Check if CAPTCHA iframe present |

### StealthBrowser

| Method | Description |
|--------|-------------|
| `launch()` | Launch browser with stealth |
| `close()` | Close browser |

## Anti-Detection

Uses playwright-stealth v2.0.2 with evasions:
- navigator.webdriver removal
- chrome.runtime injection
- WebGL fingerprint masking
- Navigator platform/language normalization
- Client Hints header normalization
- Memory-optimized Chromium args for low-RAM servers

## CAPTCHA Solving

- hCaptcha: GLM-5 Vision API + Bezier curve mouse movement
- Arkose FunCaptcha: GLM-5 Vision API analysis
- Session reuse to avoid triggering CAPTCHA

## File Locations

| File | Path |
|------|------|
| Skill package | `/root/.openclaw/workspace/skills/stealth-login/` |
| Auth states | `/root/.openclaw/workspace/auth/{service}_state.json` |
| Credentials | `/root/.openclaw/workspace/auth/credentials.json` |

## Notes

1. **Session persistence** — first login saves cookies, subsequent runs reuse them
2. **Memory** — headless Chromium ~300-500MB, optimized for 2GB servers
3. **CAPTCHA success rate** — depends on GLM-5 Vision accuracy, typically 30-50%
4. **Twitter Arkose** — harder than hCaptcha; session reuse is the best strategy
5. **MFA/Phone** — returns signal, external code must provide verification
