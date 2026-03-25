# 🚀 DevOps Monitoring Platform

A production-grade real-time system monitoring dashboard built with Flask, featuring live CPU/Memory/Disk metrics, multi-server management, and secure authentication.

## ✨ Features

- **Real-Time Monitoring** - Live CPU, Memory, and Disk usage tracking
- **Interactive Dashboard** - Beautiful charts and metrics visualization
- **Multi-Server Support** - Monitor Production and Staging environments
- **User Authentication** - Secure login/signup system
- **Live Logs** - Real-time system event streaming
- **Responsive Design** - Works on desktop and tablet
- **Professional UI** - Modern glassmorphism design with smooth animations

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd devops-project
```

### 2. Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Application
```bash
python app.py
```

The app will be available at `http://localhost:5000`

### 5. Create Your First Account
- Go to http://localhost:5000
- Click "Sign Up"
- Create a new username and password
- Login to access the dashboard

## 📁 Project Structure
```
devops-project/
├── app.py                 # Flask backend
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker configuration
├── README.md             # This file
└── templates/            # HTML templates
    ├── index.html        # Homepage
    ├── login.html        # Login page
    ├── signup.html       # Registration page
    ├── dashboard.html    # Main monitoring dashboard
    ├── metrics.html      # Detailed metrics
    ├── servers.html      # Server management
    ├── logs.html         # System logs
    ├── projects.html     # Portfolio showcase
    └── about.html        # About page
```

## 🚀 Deployment

### Local Development
**Windows:**
```bash
# Double-click: start_dev.bat
# Or run in PowerShell:
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Visit: `http://localhost:5000`

### Docker Deployment (Local)
```bash
docker-compose up -d
# Visit: http://localhost:5000
```

### 🌐 Production Deployment to trevorvaughan.dev

**Complete Guide:** See [DEPLOYMENT.md](DEPLOYMENT.md)  
**Pre-Deployment Checklist:** See [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)

#### Quick Steps:
1. **On your Linux server:**
   ```bash
   cd /home/ubuntu
   git clone <your-repo-url> devops-project
   cd devops-project
   cp .env.example .env
   nano .env  # Set SECRET_KEY
   ```

2. **Get SSL Certificate:**
   ```bash
   sudo certbot certonly --standalone -d trevorvaughan.dev -d www.trevorvaughan.dev
   ```

3. **Deploy:**
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

4. **Access:** `https://trevorvaughan.dev` ✅

#### OR Manual Deployment:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

**Result:** Your monitoring platform will be live at `https://trevorvaughan.dev` 🎉

## 🔒 Security Recommendations

1. Change the default secret key in production
2. Use environment variables for credentials
3. Enable HTTPS
4. Implement rate limiting
5. Add CSRF protection
6. Use a proper database (PostgreSQL recommended)
7. Regular security audits

## 📊 API Endpoints

- `GET /` - Homepage
- `GET /dashboard` - Main monitoring dashboard (requires login)
- `POST /login` - User login
- `POST /signup` - User registration
- `GET /logout` - Logout
- `GET /metrics` - Metrics page
- `GET /servers` - Server management
- `GET /logs` - Live logs
- `GET /api/system_info?server=<id>` - System metrics API
- `GET /api/visits` - Visit counter API

## 🎯 Next Steps

- [ ] Kubernetes deployment
- [ ] AWS infrastructure setup
- [ ] GitHub Actions CI/CD pipeline
- [ ] Database migration to PostgreSQL
- [ ] Email alerts for critical metrics
- [ ] Mobile app version
- [ ] Advanced analytics

## 👨‍💻 Author

Trevor Vaughan - DevOps Engineer

## 📝 License

MIT License
