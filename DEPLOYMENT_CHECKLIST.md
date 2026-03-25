# 📋 Pre-Deployment Checklist for trevorvaughan.dev

Before pushing to production, verify all items below:

## ✅ Code Quality
- [ ] All CSS/HTML errors fixed (verified - 36 errors fixed)
- [ ] All links working correctly
- [ ] No console errors in browser DevTools
- [ ] Tested locally: `python app.py`
- [ ] All API endpoints respond correctly

## ✅ Security
- [ ] `.env.example` created with template variables
- [ ] `.env` file (with real values) added to `.gitignore`
- [ ] `SECRET_KEY` environment variable will be set
- [ ] HTTPS/SSL will be enabled via Let's Encrypt
- [ ] Database file location is secure
- [ ] No hardcoded credentials in code

## ✅ Configuration
- [ ] `requirements.txt` contains all dependencies
- [ ] `Dockerfile` is production-ready
- [ ] `docker-compose.yml` configured correctly
- [ ] `docker-compose.prod.yml` for production stack
- [ ] `nginx.conf` ready for reverse proxy
- [ ] `.env` variables match environment setup

## ✅ Database
- [ ] SQLite database auto-initializes on first run
- [ ] Test account can be created (sign up)
- [ ] Login works correctly
- [ ] Metrics persist across restarts
- [ ] Database backup strategy planned

## ✅ DNS & Domain
- [ ] Domain `trevorvaughan.dev` points to server IP
- [ ] DNS propagation complete (can take up to 48 hours)
- [ ] Verify with: `nslookup trevorvaughan.dev`

## ✅ Server Setup
- [ ] Linux server ready (Ubuntu 20.04+)
- [ ] Docker installed
- [ ] Docker Compose installed
- [ ] Nginx installed
- [ ] Certbot installed (for SSL)
- [ ] Firewall allows ports 80, 443
- [ ] SSH access verified

## ✅ Before Going Live
- [ ] Test locally one more time
- [ ] Run: `docker-compose -f docker-compose.prod.yml up -d`
- [ ] Get SSL certificate: `certbot certonly --standalone -d trevorvaughan.dev`
- [ ] Nginx reverse proxy configured
- [ ] Visit: `https://trevorvaughan.dev`
- [ ] Test all features:
  - [ ] Homepage loads
  - [ ] Sign Up works
  - [ ] Login works
  - [ ] Dashboard shows metrics
  - [ ] Can navigate all pages
  - [ ] Metrics update every 2 seconds
  - [ ] SSL is active (🔒 in browser)

## 📊 Performance Checklist
- [ ] Page loads in < 2 seconds
- [ ] Charts render smoothly
- [ ] No memory leaks in console
- [ ] API responses < 500ms
- [ ] Metrics update without lag

## 🔒 Post-Deployment
- [ ] Monitor for 24 hours
- [ ] Check error logs: `docker-compose logs -f web`
- [ ] Set up auto-backups of database
- [ ] Monitor disk space
- [ ] Plan SSL renewal (auto with certbot)
- [ ] Document any custom changes

## 🚨 Emergency Procedures
If something breaks after deployment:

1. **Can't access site**
   ```bash
   docker-compose logs web
   docker-compose restart
   ```

2. **Database issues**
   ```bash
   docker-compose exec web rm metrics.db
   docker-compose restart
   ```

3. **SSL certificate error**
   ```bash
   sudo certbot renew
   sudo systemctl reload nginx
   ```

4. **High resource usage**
   ```bash
   docker stats
   docker-compose down && docker-compose up -d
   ```

## 📞 Support Resources
- Deployment Guide: `DEPLOYMENT.md`
- Flask Docs: https://flask.palletsprojects.com/
- Docker Docs: https://docs.docker.com/
- Let's Encrypt: https://letsencrypt.org/

---

**Ready to deploy?** Follow `DEPLOYMENT.md` for step-by-step instructions.
