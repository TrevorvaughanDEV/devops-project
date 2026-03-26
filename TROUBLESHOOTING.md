# 🔧 Troubleshooting Guide

## API Error 500 (Fixed ✅)

### Root Cause
The original code had a **variable shadowing bug** where the function `def servers():` was overwriting the global `servers` dictionary, causing the API to fail when trying to access server information.

### Solution Applied
✅ Renamed the global dictionary to `SERVER_INFO`
✅ Renamed route functions to avoid conflicts (e.g., `servers_page()`)
✅ Added comprehensive error handling and logging
✅ Improved database connection management

---

## If You Still See Errors

### Option 1: Clear Database & Restart
```bash
# Delete the old database to force recreation
rm metrics.db
# Or on Windows:
del metrics.db

# Restart Flask
python app.py
```

### Option 2: Check Flask Console for Errors
Look at the terminal where Flask is running. Errors will be printed there with full traceback.

### Option 3: Test API Directly
Open your browser and visit:
```
http://localhost:5000/api/system_info?server=server1
```

Should return JSON like:
```json
{
  "server": "Production",
  "cpu": 25.5,
  "memory": 45.2,
  "disk": 32.1,
  "alerts": [],
  "timestamp": "2026-03-26T10:30:45.123456"
}
```

---

## Common Issues

### "Database is locked"
**Cause:** Flask app already running in another terminal
**Fix:** Kill the process on port 5000
```bash
# Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# macOS/Linux
lsof -ti:5000 | xargs kill -9
```

### "ModuleNotFoundError: No module named 'xyz'"
**Fix:** Reinstall requirements
```bash
pip install -r requirements.txt --upgrade
```

### "Template not found"
**Cause:** Running from wrong directory
**Fix:** Make sure you're in the project root where `templates/` folder exists
```bash
cd /path/to/devops-project
python app.py
```

### Charts Not Loading
**Fix:** 
1. Check browser console (F12 → Console tab)
2. Verify Chart.js CDN is loaded
3. Ensure API returns proper JSON

### Slow Dashboard Response
**Fix:**
1. Clear browser cache (Ctrl+Shift+Delete)
2. Restart Flask app
3. Check CPU/Memory usage on your machine

---

## Production Deployment

For production on your domain (trevorvaughan.dev), use the Docker setup:

```bash
# Build Docker image
docker build -t devops-monitor .

# Run with Docker Compose (production)
docker-compose -f docker-compose.prod.yml up -d
```

See **DEPLOYMENT.md** for detailed production setup.

---

## Debugging Commands

### Check if Flask is running
```bash
curl http://localhost:5000/
```

### Test API endpoint
```bash
curl http://localhost:5000/api/system_info?server=server1
```

### View Flask logs in real-time
```bash
# Terminal will show all logs as they happen
python app.py
```

### Check database
```bash
sqlite3 metrics.db
> SELECT * FROM users;
> .quit
```

---

## Still Having Issues?

1. **Clear everything and restart:**
   - Delete `metrics.db`
   - Close all Flask terminals
   - `pip install -r requirements.txt`
   - `python app.py`

2. **Check all files are in place:**
   - ✅ `app.py`
   - ✅ `requirements.txt`
   - ✅ `templates/` folder with all HTML files
   - ✅ `metrics.db` (auto-created on first run)

3. **Test authentication:**
   - Sign up with test account
   - Login with credentials
   - Navigate to dashboard

4. **Monitor the Flask console** - it will show exactly what's breaking

---

## Performance Tips

- **Use Chrome DevTools (F12)** → Network tab to see API response times
- **Dashboard slower on first load?** Normal - it's loading 20 chart data points
- **Multiple users?** Not currently supported locally, but production Docker setup handles this
- **Too many requests?** Change the poll interval in dashboard.html from 2000ms to higher value

---

## Support

If issues persist:
1. Check the Flask console output - it has the exact error message
2. Review the error output in browser console (F12)
3. Verify all dependencies: `pip list`
4. Ensure Python 3.8+ is installed: `python --version`
