# 🚀 Deployment Guide for trevorvaughan.dev

This guide walks you through deploying the DevOps Monitoring Platform to your domain.

## Prerequisites

- Linux server (Ubuntu 20.04+ recommended)
- SSH access to your server
- Domain pointing to your server's IP
- Docker and Docker Compose installed
- Nginx installed (for reverse proxy)
- SSL Certificate (Let's Encrypt)

---

## 1. Server Setup

### Install Docker & Docker Compose
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Add user to docker group
sudo usermod -aG docker $USER
```

### Install Nginx
```bash
sudo apt install nginx -y
sudo systemctl start nginx
sudo systemctl enable nginx
```

### Install Certbot for SSL
```bash
sudo apt install certbot python3-certbot-nginx -y
```

---

## 2. Clone & Configure

### Clone Repository
```bash
cd /home/ubuntu
git clone <your-repo-url> devops-project
cd devops-project
```

### Create Environment File
```bash
cp .env.example .env
nano .env
```

**Update `.env` with:**
```
FLASK_ENV=production
SECRET_KEY=<generate-a-random-256-char-key>
```

**Generate a secure key:**
```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

---

## 3. SSL Certificate Setup

### Get SSL Certificate from Let's Encrypt
```bash
sudo certbot certonly --standalone -d trevorvaughan.dev -d www.trevorvaughan.dev
```

This creates certificates at:
- `/etc/letsencrypt/live/trevorvaughan.dev/fullchain.pem`
- `/etc/letsencrypt/live/trevorvaughan.dev/privkey.pem`

### Auto-Renewal
```bash
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

---

## 4. Deploy with Docker Compose

### Build & Run
```bash
cd /home/ubuntu/devops-project
docker-compose up -d
```

### Verify It's Running
```bash
docker-compose ps
docker-compose logs -f
```

---

## 5. Configure Nginx Reverse Proxy

### Copy Nginx Config
```bash
sudo cp nginx.conf /etc/nginx/sites-available/devops-monitor
sudo ln -s /etc/nginx/sites-available/devops-monitor /etc/nginx/sites-enabled/
```

### Remove Default Config
```bash
sudo rm /etc/nginx/sites-enabled/default
```

### Test & Reload Nginx
```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## 6. Verify Deployment

### Check Application
```bash
# Check if service is running
curl http://localhost:5000

# Check logs
docker-compose logs web
```

### Access via Domain
Visit: `https://trevorvaughan.dev`

You should see:
- ✅ Homepage loads
- ✅ Sign Up works
- ✅ Dashboard accessible after login
- ✅ Metrics load live
- ✅ SSL is active (🔒)

---

## 7. Update & Maintenance

### Update Code
```bash
cd /home/ubuntu/devops-project
git pull origin main
docker-compose up -d --build
```

### View Logs
```bash
docker-compose logs -f web
```

### Restart
```bash
docker-compose restart
```

### Backup Database
```bash
cp metrics.db metrics.db.backup
```

---

## 8. Troubleshooting

### Application not running
```bash
docker-compose down
docker-compose up -d --build
```

### Port already in use
```bash
sudo lsof -i :5000
```

### Database locked
```bash
rm metrics.db
docker-compose restart
```

### SSL issues
```bash
sudo certbot renew --dry-run
sudo systemctl reload nginx
```

---

## 9. Security Checklist

- ✅ Change `SECRET_KEY` in `.env`
- ✅ Enable SSL/HTTPS
- ✅ Keep Docker images updated
- ✅ Enable firewall rules
- ✅ Set up monitoring/alerts
- ✅ Regular backups of database
- ✅ Use strong admin credentials

---

## 10. Health Monitoring

### Check Application Health
```bash
# Via Docker
docker-compose exec web curl http://localhost:5000

# Via Nginx
curl https://trevorvaughan.dev --insecure
```

### Monitor Resources
```bash
docker stats
```

---

## 11. Systemd Service File (Optional)

Create `/etc/systemd/system/devops-monitor.service`:
```ini
[Unit]
Description=DevOps Monitoring Platform
After=docker.service
Requires=docker.service

[Service]
Type=simple
WorkingDirectory=/home/ubuntu/devops-project
ExecStart=/usr/local/bin/docker-compose up
ExecStop=/usr/local/bin/docker-compose down
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable devops-monitor
sudo systemctl start devops-monitor
```

---

## Support

For issues, check:
1. Docker logs: `docker-compose logs`
2. Nginx logs: `sudo tail -f /var/log/nginx/devops_monitor_error.log`
3. System logs: `sudo journalctl -u docker`

Happy deploying! 🚀
