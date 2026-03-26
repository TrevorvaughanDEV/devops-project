# ⚡ Quick Start Guide

## 🚀Get Running in 2 Minutes

### Step 1: Open Terminal/PowerShell
Navigate to the project folder:
```bash
cd c:\Users\Trevor\Documents\devops-project
```

### Step 2: Activate Virtual Environment
```bash
# Create if you don't have one
python -m venv venv

# Activate it
venv\Scripts\activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Start the App
```bash
python app.py
```

You should see:
```
 * Running on http://127.0.0.1:5000
```

### Step 5: Open in Browser
Visit: **http://localhost:5000**

---

## 📝 First Login

1. Click **"Sign Up"**
2. Create account with any username/password
3. You're logged in! Welcome to the dashboard

---

## ✨ What's Working Now

✅ **Dashboard** - Real-time CPU/Memory/Disk metrics with beautiful charts
✅ **Server Selection** - Switch between Production & Staging
✅ **Visitor Tracking** - Shows total visits
✅ **Alerts** - Warns when resources exceed 80%
✅ **All Navigation Links** - Metrics, Servers, Logs, Projects, About pages
✅ **Error Handling** - Gracefully handles API failures
✅ **Beautiful UI** - Modern glassmorphism design

---

## 🔍 Verify Everything Works

### Test 1: Check Homepage
Visit: `http://localhost:5000/`
- Should show landing page with live metrics preview bars

### Test 2: Check API Directly
Visit: `http://localhost:5000/api/system_info?server=server1`
- Should see JSON response with cpu, memory, disk values

### Test 3: Sign Up & Login
1. Go to homepage and click "Sign Up"
2. Create test account: `testuser` / `password123`
3. Login with same credentials
4. Should see colorful dashboard with metrics

### Test 4: Dashboard Metrics
- Charts should update every 2 seconds
- Values change in real-time
- Alerts appear when CPU/Memory >80%

---

## 📊 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Homepage |
| `/login` | GET/POST | User login |
| `/signup` | GET/POST | User registration |
| `/dashboard` | GET | Main dashboard (requires login) |
| `/metrics` | GET | Metrics page |
| `/servers` | GET | Servers page |
| `/logs` | GET | Logs page |
| `/projects` | GET | Projects page |
| `/about` | GET | About page |
| `/api/system_info` | GET | Real-time system metrics |
| `/api/visits` | GET | Total visitor count |
| `/logout` | GET | Logout user |

---

## 🛑 If Something Breaks

### Clear & Reset Everything
```bash
# Delete database
del metrics.db

# Delete cache
del .python-version

# Reinstall dependencies
pip install -r requirements.txt --upgrade --force-reinstall

# Start fresh
python app.py
```

### Check Logs
- **Flask Console** shows all errors in real-time
- **Browser Console** (F12 → Console) shows frontend errors
- Look there first when something doesn't work!

---

## 📱 Access from Another Computer

While Flask is running on your machine, you can access it from another computer:
```
http://<your-computer-ip>:5000/
```

To find your IP:
```bash
ipconfig
# Look for "IPv4 Address" under active network
```

---

## 🎯 Next Steps

1. ✅ Verify everything works locally
2. 📝 Create accounts and test features
3. 🐳 When ready, deploy with Docker to `trevorvaughan.dev`
4. 📖 See `DEPLOYMENT.md` for production setup

---

## 💡 Pro Tips

- **Clear browser cache** (Ctrl+Shift+Delete) if charts don't update
- **Check Flask console** first when API returns errors
- **Use F12 → Network** to see API requests/responses
- **Bookmark localhost:5000** for quick access during testing

---

Happy monitoring! 🚀
