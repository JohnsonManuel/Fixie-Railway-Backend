# Railway Deployment Guide

## 🚂 Deploying to Railway

### Prerequisites
1. GitHub account
2. Railway account (free at railway.app)
3. Your API keys ready

### Step 1: Push to GitHub
```bash
cd python-backend
git init
git add .
git commit -m "Initial commit for Railway deployment"
git branch -M main
git remote add origin https://github.com/yourusername/your-repo-name.git
git push -u origin main
```

### Step 2: Deploy on Railway
1. Go to [railway.app](https://railway.app)
2. Sign up/login with GitHub
3. Click "New Project"
4. Select "Deploy from GitHub repo"
5. Choose your repository
6. Railway will auto-detect Python and deploy!

### Step 3: Set Environment Variables
In Railway dashboard, go to Variables tab and add:

```
OPENAI_API_KEY=your-actual-openai-key
FRESHDESK_DOMAIN=yourcompany.freshdesk.com
FRESHDESK_API_KEY=your-actual-freshdesk-key
FRONTEND_URL=https://your-frontend-domain.com
```

### Step 4: Get Your URL
Railway will give you a URL like: `https://your-app-name.up.railway.app`

### Step 5: Update Frontend
Update your frontend to use the Railway URL instead of Firebase Functions.

## 🔧 Debugging
- View logs in Railway dashboard
- Real-time log streaming
- Easy rollbacks
- Environment variable management

## 💰 Cost
- Free tier: 500 hours/month
- $5/month for unlimited usage
- Very affordable!

## 🚀 Benefits over Firebase Functions
- ✅ Easy debugging with real-time logs
- ✅ No complex deployment process
- ✅ Simple environment variable management
- ✅ Instant rollbacks
- ✅ Better performance
- ✅ No cold starts

