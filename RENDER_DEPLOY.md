# 🚀 RENDER DEPLOYMENT GUIDE

## ✅ Step 1: Create GitHub Repository

Your code is ready to push to GitHub. Choose one:

### Option A: Create New Repository (5 minutes)

1. Go to **[github.com/new](https://github.com/new)**
2. Sign in (create account if needed - FREE)
3. Fill in:
   - **Repository name:** `fb-auto-poster`
   - **Description:** "Facebook Group Auto Poster - Batch posting automation"
   - **Public** or **Private** (doesn't matter)
4. Click **"Create repository"**
5. GitHub shows you commands. Use these:

```bash
cd c:\Users\AWST\Desktop\fb-group-auto-post-main

# Add remote
git remote add origin https://github.com/YOUR_USERNAME/fb-auto-poster.git
git branch -M main
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub username.

---

## ✅ Step 2: Deploy on Render

1. Go to **[render.com](https://render.com)**
2. Click **"Sign up"** → Choose **"Continue with GitHub"**
3. Authorize Render to access your GitHub account
4. You're logged in! Now:
5. Click **"New +"** button (top right)
6. Select **"Web Service"**
7. Find `fb-auto-poster` repository and click **"Connect"**
8. Fill in settings:

| Field | Value |
|-------|-------|
| **Name** | `fb-auto-poster` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python run_server.py` |
| **Instance Type** | `Free` |

9. Click **"Create Web Service"**
10. **Wait 3-5 minutes** for deployment

---

## 🎉 Your App is LIVE!

After deployment, Render shows your URL:

```
https://fb-auto-poster.onrender.com
```

**Use these credentials to login:**
```
Username: admin
Password: password123
```

---

## 📝 Automatic Redeploy

Every time you push to GitHub, Render automatically redeploys:

```bash
git add .
git commit -m "Your changes"
git push origin main
# 🚀 Automatically deploys on Render!
```

---

## 🔧 Environment Variables (Optional)

To customize settings:

1. Go to your Render dashboard
2. Click your service → **Settings**
3. Scroll to **Environment Variables**
4. Add variables (optional):

```
FLASK_ENV=production
DEBUG_MODE=false
PYTHONUNBUFFERED=1
```

---

## ⚡ Important Notes

### Free Tier Features (First 3 Months)
✅ **Unlimited uptime** (24/7 running)
✅ **Free hosting** (no credit card charged yet)
✅ **Auto HTTPS** (SSL included)
✅ **Automatic deployments** (push to GitHub = auto deploy)
✅ **Persistent storage** (your data saved)

### After 3 Months
- **Cost:** ~$7/month (Standard instance)
- **Feature:** Always-on (no sleeping)
- Choose to pay or delete to restart free trial

---

## 🆘 Troubleshooting

### "Service Unavailable"?
1. Click **"Manual Deploy"** button in Render dashboard
2. Check **Logs** tab for errors
3. Wait 1-2 minutes for deployment to complete

### Login not working?
1. Check browser cookies are enabled
2. Try in private/incognito window
3. Check Render logs for errors

### How to check logs?
1. Go to Render dashboard
2. Click your service `fb-auto-poster`
3. Click **Logs** tab
4. See what's happening

---

## 📊 Monitor Your Deployment

In Render dashboard:
- **Logs** → See real-time errors & activity
- **Metrics** → Monitor CPU, memory, requests
- **Settings** → Change environment variables
- **Deployments** → See deployment history

---

## 💻 Local Testing (Before Deployment)

Make sure server works locally first:

```bash
cd c:\Users\AWST\Desktop\fb-group-auto-post-main
python run_server.py
```

Access: `http://localhost:5000`
Login: `admin` / `password123`

---

## 🎯 Next Steps After Deployment

1. **Test the app** - Login, create some posts
2. **Update password** - Change from default credentials
3. **Set up Facebook** - Add your Facebook account
4. **Create groups list** - Add Facebook groups to target
5. **Start posting!** - Create your first batch post

---

## 📞 Questions?

- **Render Support:** [docs.render.com](https://docs.render.com)
- **GitHub Help:** [docs.github.com](https://docs.github.com)

---

## 🚀 Quick Command Reference

```bash
# Create new repo on GitHub
git remote add origin https://github.com/YOUR_USERNAME/fb-auto-poster.git
git branch -M main
git push -u origin main

# Update after making changes
git add .
git commit -m "Your changes"
git push origin main

# Check deployment
# Go to https://render.com/dashboard
```

**You're ready to deploy!** 🎉
