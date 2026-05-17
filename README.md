# InstaFlow — Instagram Comment-to-DM Automation

Automatically reply to Instagram comments and send DMs when someone comments a trigger keyword on your posts. Built on the **official Instagram Graph API** — no unofficial libraries, no Selenium.

```
Comment "link" on your post
  ↓
InstaFlow detects it
  ↓
Public reply: "Hey! Just sent you a DM 📩"
  ↓
Private DM: "Here's the link: https://..."
```

---

## Table of Contents

1. [Instagram API Setup (Start Here)](#1-instagram-api-setup-start-here)
2. [Running Locally](#2-running-locally)
3. [Webhook Configuration](#3-webhook-configuration)
4. [Finding Your Post ID](#4-finding-your-post-id)
5. [Refreshing Your Access Token](#5-refreshing-your-access-token)
6. [Deploying to the Cloud](#6-deploying-to-the-cloud)
7. [Environment Variables Reference](#7-environment-variables-reference)
8. [DM Limitation & How to Apply for Permission](#8-dm-limitation--how-to-apply-for-permission)
9. [Project Structure](#9-project-structure)
10. [API Reference](#10-api-reference)

---

## 1. Instagram API Setup (Start Here)

Follow these steps **in order**. This takes about 20–30 minutes the first time.

### Step 1 — Convert Instagram Account to Business or Creator

1. Open the Instagram app
2. Go to **Settings → Account → Switch to Professional Account**
3. Choose **Business** or **Creator**
4. Connect it to a Facebook Page (create one if you don't have one)

> You must have a Facebook Page linked to your Instagram account for the Graph API to work.

---

### Step 2 — Create a Facebook Developer App

1. Go to [developers.facebook.com](https://developers.facebook.com)
2. Click **My Apps → Create App**
3. Choose **"Other"** as the use case → **"Business"** as the type
4. Enter an app name (e.g. "InstaFlow") and your contact email
5. Click **Create App**

---

### Step 3 — Add the Instagram Graph API Product

1. In your app dashboard, click **"Add Product"**
2. Find **Instagram Graph API** and click **Set Up**
3. You'll now see Instagram in your left sidebar

---

### Step 4 — Add Required Permissions

Go to **App Review → Permissions and Features** and request:

| Permission | Purpose |
|---|---|
| `instagram_manage_comments` | Read comments and post replies |
| `instagram_manage_messages` | Send DMs to users |
| `instagram_basic` | Read basic account info |
| `pages_read_engagement` | Read page data |

> For testing, you can use these permissions in **Development mode** without App Review — but only for accounts added as testers in your app.

To add test accounts:
1. Go to **Roles → Test Users** or **Roles → Roles**
2. Add your Instagram account as an admin/tester

---

### Step 5 — Get Your Access Token

#### Option A — Graph API Explorer (quickest for testing)

1. Go to [developers.facebook.com/tools/explorer](https://developers.facebook.com/tools/explorer)
2. Select your app from the dropdown
3. Click **"Generate Access Token"**
4. Grant all requested permissions
5. Copy the **User Access Token**

This is a **short-lived token** (valid ~1 hour). Convert it to a long-lived token below.

#### Convert to Long-Lived Token (valid 60 days)

Run this in your terminal:

```bash
curl -X GET "https://graph.facebook.com/v19.0/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id=YOUR_APP_ID
  &client_secret=YOUR_APP_SECRET
  &fb_exchange_token=YOUR_SHORT_LIVED_TOKEN"
```

Replace `YOUR_APP_ID`, `YOUR_APP_SECRET`, and `YOUR_SHORT_LIVED_TOKEN` with your actual values.

You'll get a response like:
```json
{
  "access_token": "EAAGm0...",
  "token_type": "bearer",
  "expires_in": 5183944
}
```

Save this `access_token` — it's valid for ~60 days.

---

### Step 6 — Get Your Instagram Business Account ID

1. Go to Graph API Explorer
2. Make a GET request to: `me/accounts`
3. Find your Facebook Page in the response
4. From the page's `id`, make a GET request to: `/{page-id}?fields=instagram_business_account`
5. The `instagram_business_account.id` is your **Instagram Business Account ID**

Alternatively, use this single call (replace `PAGE_ID` and `ACCESS_TOKEN`):

```bash
curl "https://graph.facebook.com/v19.0/PAGE_ID?fields=instagram_business_account&access_token=ACCESS_TOKEN"
```

---

### Step 7 — Get Your Page ID

1. Go to your Facebook Page
2. Click **About** (or **Page Info** on desktop)
3. Scroll down to find **Page ID**

Or via API:
```bash
curl "https://graph.facebook.com/v19.0/me/accounts?access_token=ACCESS_TOKEN"
```

---

## 2. Running Locally

### Prerequisites

- Python 3.11+
- pip

### Setup

```bash
# Clone the repo
git clone <your-repo-url>
cd instagram-automation

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy env file and fill in your values
cp .env.example .env
nano .env  # or open in your editor
```

Fill in `.env`:

```env
INSTAGRAM_ACCESS_TOKEN=EAAGm0...
INSTAGRAM_BUSINESS_ACCOUNT_ID=12345...
FACEBOOK_PAGE_ID=98765...
FACEBOOK_APP_SECRET=abc123...
FACEBOOK_APP_ID=111222...
WEBHOOK_VERIFY_TOKEN=my-random-secret-string
```

### Run the server

```bash
uvicorn main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000) — the dashboard will appear.

---

## 3. Webhook Configuration

Facebook must be able to reach your server to send webhook events. During development, use a tunnel:

### Using ngrok (free)

```bash
# Install ngrok: https://ngrok.com/download
ngrok http 8000
```

You'll get a URL like `https://abc123.ngrok.io`. Your webhook URL is:
```
https://abc123.ngrok.io/webhook/instagram
```

### Registering the Webhook in Facebook

1. In your Facebook App Dashboard, go to **Webhooks** (in the left sidebar)
2. Click **Add Subscriptions** or **Edit**
3. Set:
   - **Callback URL**: `https://your-domain.com/webhook/instagram`
   - **Verify Token**: Same value as `WEBHOOK_VERIFY_TOKEN` in your `.env`
4. Click **Verify and Save**
5. Under the subscription, select the `comments` field and click **Subscribe**

> The app must be running when you click Verify — Facebook will immediately send a GET challenge request.

### Subscribing to Your Instagram Account's Comments

After configuring the webhook, subscribe your Instagram account:

```bash
curl -X POST \
  "https://graph.facebook.com/v19.0/YOUR_PAGE_ID/subscribed_apps" \
  -d "subscribed_fields=feed,comments" \
  -d "access_token=YOUR_PAGE_ACCESS_TOKEN"
```

Note: Use your **Page Access Token** (from `me/accounts` response), not the User Access Token.

---

## 4. Finding Your Post ID

### Method 1 — Graph API Explorer

1. Open [developers.facebook.com/tools/explorer](https://developers.facebook.com/tools/explorer)
2. Make a GET request to:
   ```
   /{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media?fields=id,caption,media_type,timestamp
   ```
3. Find your post in the list — the `id` field is the **Post ID**

### Method 2 — Instagram URL

From a post's URL like `https://www.instagram.com/p/ABC123xyz/`:
1. Copy the shortcode (`ABC123xyz`)
2. Use the API to resolve it:
   ```bash
   curl "https://graph.facebook.com/v19.0/ig_hashtag_search?ig_hashtag=ABC123xyz&access_token=TOKEN"
   ```

### Method 3 — Dashboard Preview

In the InstaFlow dashboard, go to **New Campaign**, paste a Post ID, and click **Preview** — it will fetch and show the post thumbnail and caption so you can confirm it's the right post.

---

## 5. Refreshing Your Access Token

Long-lived tokens expire after **60 days**. Refresh them before they expire:

```bash
curl "https://graph.facebook.com/v19.0/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id=YOUR_APP_ID
  &client_secret=YOUR_APP_SECRET
  &fb_exchange_token=YOUR_CURRENT_LONG_LIVED_TOKEN"
```

> Best practice: Set a calendar reminder 50 days after issuing a token.

You can also refresh the token in the InstaFlow dashboard under **Settings → Save Credentials** — just paste the new token and save.

---

## 6. Deploying to the Cloud

### Railway (recommended — 1-click)

1. Push your code to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Select your repo
4. Add environment variables in the Railway dashboard
5. Railway will auto-detect the `Dockerfile` and deploy

The `railway.toml` is already configured.

### Render

1. Go to [render.com](https://render.com) → New → Web Service
2. Connect your GitHub repo
3. Render will detect the `render.yaml`
4. Add environment variables in the Render dashboard

### Docker (any VPS)

```bash
docker build -t instaflow .

docker run -d \
  -p 8000:8000 \
  -v /path/to/data:/data \
  -e INSTAGRAM_ACCESS_TOKEN=... \
  -e INSTAGRAM_BUSINESS_ACCOUNT_ID=... \
  -e FACEBOOK_PAGE_ID=... \
  -e FACEBOOK_APP_SECRET=... \
  -e WEBHOOK_VERIFY_TOKEN=... \
  --name instaflow \
  instaflow
```

### After Deployment

1. Update your Facebook webhook URL to your production URL
2. Verify the webhook again in the Facebook App Dashboard
3. Visit `/health` to confirm the app is running

---

## 7. Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `INSTAGRAM_ACCESS_TOKEN` | Yes | Long-lived User Access Token from Graph API |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | Yes | Your IG Business Account ID (numeric) |
| `FACEBOOK_PAGE_ID` | Yes | Your Facebook Page ID (numeric) |
| `FACEBOOK_APP_SECRET` | Yes | From your Facebook App → Settings → Basic |
| `FACEBOOK_APP_ID` | Yes | From your Facebook App → Settings → Basic |
| `WEBHOOK_VERIFY_TOKEN` | Yes | Any random string; must match what you put in Facebook webhook settings |
| `DATABASE_URL` | No | Defaults to `sqlite+aiosqlite:///./app.db`. For Postgres: `postgresql+asyncpg://user:pass@host/db` |
| `DEBUG` | No | Set to `true` for verbose logging |

---

## 8. DM Limitation & How to Apply for Permission

### The Limitation

Instagram's API **cannot send DMs to any arbitrary user**. There are two conditions under which it works:

1. **The user has previously messaged your Instagram account** (i.e., an existing conversation thread exists)
2. **Your app has been approved for proactive messaging** via the `instagram_manage_messages` advanced permission

### For Testing

During development, DMs work if the commenter has previously sent you a DM on Instagram. This is the easiest way to test end-to-end.

### Applying for Proactive Messaging Permission

To send DMs to anyone who comments (not just existing conversationists):

1. In your Facebook App Dashboard → **App Review → Permissions and Features**
2. Find `instagram_manage_messages`
3. Click **Request Advanced Access**
4. Complete the business verification (you'll need a business portfolio)
5. Submit a screencast showing how your app uses DMs
6. Meta reviews within 5–7 business days

> Note: Meta requires that DMs are relevant and expected by the recipient. Automation that sends unsolicited spam will be rejected. Use clear opt-in language in your comment reply (e.g., "I've sent you a DM with the details you asked for!").

### What Happens When DM Fails

InstaFlow logs the failure and records `dm_sent = false` in the `processed_comments` table. The comment reply is still sent (these are independent operations). You can monitor failures in the **Activity** tab of the dashboard.

---

## 9. Project Structure

```
├── main.py                  # FastAPI app entry point + lifespan
├── instagram.py             # Instagram Graph API client (comments, DMs, post details)
├── models.py                # SQLAlchemy ORM models (Config, Campaign, ProcessedComment)
├── database.py              # Async DB engine + session factory
├── routes/
│   ├── __init__.py
│   ├── webhook.py           # POST /webhook/instagram (event handler)
│   │                        # GET  /webhook/instagram (challenge verification)
│   ├── api.py               # REST API: /api/campaigns, /api/config, /api/stats, etc.
│   └── dashboard.py         # Serves the HTML dashboard
├── static/
│   ├── css/dashboard.css    # Dark industrial UI styles
│   └── js/dashboard.js      # SPA logic (nav, CRUD, modals, toasts)
├── templates/
│   └── dashboard.html       # Jinja2 HTML template
├── .env.example             # Template for environment variables
├── Dockerfile               # Multi-stage Docker build
├── railway.toml             # Railway deployment config
├── render.yaml              # Render deployment config
├── requirements.txt
└── README.md
```

---

## 10. API Reference

### Health

```
GET /health
→ {"status": "ok"}
```

### Webhook

```
GET  /webhook/instagram   — Facebook challenge verification
POST /webhook/instagram   — Receive comment events (Facebook → InstaFlow)
```

### Config

```
GET  /api/config          — Get current config (token masked)
POST /api/config          — Save credentials
POST /api/config/verify   — Test credentials against Instagram API
```

### Campaigns

```
GET    /api/campaigns              — List all campaigns
POST   /api/campaigns              — Create campaign
GET    /api/campaigns/{id}         — Get single campaign
PUT    /api/campaigns/{id}         — Update campaign
DELETE /api/campaigns/{id}         — Delete campaign
PATCH  /api/campaigns/{id}/toggle  — Toggle active/inactive
```

### Utility

```
GET /api/post-preview?post_id=...  — Fetch post thumbnail + caption
GET /api/activity?limit=50         — Recent processed comments
GET /api/stats                     — Aggregate counts
```

---

## Troubleshooting

**Webhook verification fails**
- Make sure the app is running and publicly accessible
- Check that `WEBHOOK_VERIFY_TOKEN` in `.env` matches what you entered in Facebook

**"Missing credentials" error**
- Add credentials in the dashboard Settings tab, OR set environment variables
- Click "Verify Connection" to test them

**Comments not triggering automation**
- Confirm the Post ID is correct (use the Preview button)
- Make sure the campaign is set to Active
- Check that your webhook subscription includes `comments` field
- Look at server logs for `[webhook]` entries

**DMs not sending**
- Expected if the commenter has never messaged your account — see [Section 8](#8-dm-limitation--how-to-apply-for-permission)
- Check Activity log for `dm_sent: false` entries and associated error logs

**Rate limit errors**
- InstaFlow automatically retries with exponential backoff (5s, 10s, 20s)
- If you're hitting limits frequently, consider reducing campaign count or test traffic
