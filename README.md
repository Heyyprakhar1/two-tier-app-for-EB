# DevOps Deployment Dashboard

A simple, beginner-friendly **two-tier web application** built with **Flask** and **MySQL**, containerized with **Docker**, and designed to be **AWS Elastic Beanstalk-ready**.

---

## 1. Architecture

```text
Browser  ─── HTTP (Port 5000) ───▶  Flask Application (Gunicorn)  ─── Port 3306 ───▶  MySQL Database
```

- **Tier 1 (Application Layer):** Flask web server running with Gunicorn WSGI, rendering dynamic HTML templates and handling deployment CRUD logic.
- **Tier 2 (Database Layer):** MySQL 8.x storing deployment history and status metrics.
  - **Local Development:** MySQL runs as a container managed by Docker Compose with a persistent named volume.
  - **AWS Elastic Beanstalk / Production:** The Flask container connects to an external, managed database such as **Amazon RDS (MySQL)**.

---

## 2. Features

- **Live Deployment Dashboard:** View all deployment events stored in MySQL, ordered newest first.
- **Metric Summary Cards:** Instant overview of Total, Successful, In-Progress, and Failed deployments.
- **Record Deployments:** Form with input validation (Application Name, Version, Environment, Status).
- **Delete Deployments:** Safe deletion with confirmation prompt.
- **Empty State Display:** Clear guidance when no deployments exist in the database.
- **Resilient Database Retries:** Flask automatically retries MySQL connections during startup or transient network blips without crashing.
- **Production WSGI Server:** Powered by Gunicorn with multi-worker concurrency.
- **Lightweight Health Check (`/health`):** Verifies application and database connectivity without exposing sensitive credentials or topology.
- **Elastic Beanstalk Compatible:** Standard single-container Dockerfile at the repository root binding to port 5000.

---

## 3. Tech Stack

- **Backend / Web:** Python 3.12, Flask 3.x, Gunicorn 23.x
- **Database Driver:** PyMySQL with cryptography (caching_sha2_password support)
- **Database:** MySQL 8.x
- **Containerization:** Docker, Docker Compose

---

## 4. Project Structure

```text
multi-tier-app-for-EB/
├── Dockerfile              # Production Dockerfile for Flask app (Gunicorn on port 5000)
├── docker-compose.yml      # Local dev multi-container setup (Flask + MySQL)
├── requirements.txt        # Python dependencies
├── app.py                  # Flask application routes, validation, and DB logic
├── .env.example            # Sample environment variables
├── .dockerignore           # Excludes git, caches, and secrets from Docker builds
├── .gitignore              # Excludes secrets, caches, and virtual environments
├── database/
│   └── init.sql            # Database schema and initial seed data
├── templates/
│   └── index.html          # Server-rendered HTML dashboard template
├── static/
│   └── style.css           # Lightweight, responsive CSS styling
└── README.md               # Project documentation and deployment guide
```

---

## 5. Quick Start (Local Development)

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (v20.10+)
- [Docker Compose](https://docs.docker.com/compose/) (v2.0+)

### Step 1: Clone and Enter the Directory

```bash
git clone git@github.com:Heyyprakhar1/multi-tier-app-for-EB.git
cd multi-tier-app-for-EB
```

### Step 2: (Optional) Create Local Environment File

```bash
cp .env.example .env
```

### Step 3: Start Application and Database

```bash
docker compose up --build
```

Docker Compose will:
1. Start the MySQL 8.4 database container and run `database/init.sql`.
2. Wait for MySQL's health check (`mysqladmin ping`) to report healthy.
3. Build and launch the Flask application container with Gunicorn on port `5000`.

### Step 4: Access the Application

- **Dashboard:** [http://localhost:5000](http://localhost:5000)
- **Health Check:** [http://localhost:5000/health](http://localhost:5000/health)
- **Deployments API (JSON):** [http://localhost:5000/api/deployments](http://localhost:5000/api/deployments)
- **Statistics API (JSON):** [http://localhost:5000/api/stats](http://localhost:5000/api/stats)

---

## 6. Environment Variables

The application is configured entirely via environment variables.

| Variable | Description | Default (Local Compose) |
|---|---|---|
| `PORT` | Port Flask/Gunicorn listens on | `5000` |
| `SECRET_KEY` | Flask session & flash message secret key | `change-this-in-production` |
| `MYSQL_HOST` | MySQL hostname or endpoint | `database` (or Amazon RDS endpoint) |
| `MYSQL_PORT` | MySQL connection port | `3306` |
| `MYSQL_DB` | Database name | `devops_dashboard` |
| `MYSQL_USER` | MySQL username | `dashboard` |
| `MYSQL_PASSWORD` | MySQL user password | `dashboard123` |
| `MYSQL_ROOT_PASSWORD`| Root password for local MySQL container | `rootpassword123` |

---

## 7. Verifying Data Persistence

The database uses a Docker named volume (`mysql_data`). Records persist across container restarts.

Test persistence:
1. Open [http://localhost:5000](http://localhost:5000) and create a new deployment (e.g. `auth-service` / `v1.0.0` / `staging` / `SUCCESS`).
2. Stop the containers:
   ```bash
   docker compose down
   ```
3. Restart the containers:
   ```bash
   docker compose up -d
   ```
4. Refresh [http://localhost:5000](http://localhost:5000) — all deployments remain intact.

To reset the database cleanly:
```bash
docker compose down -v
docker compose up --build
```

---

## 8. AWS Elastic Beanstalk Deployment Guide

When deploying to AWS Elastic Beanstalk, follow standard cloud best practices:
1. **Application Layer (EB):** Run the Flask application container on an Elastic Beanstalk **Docker environment**.
2. **Database Layer (RDS):** Provision a managed **Amazon RDS for MySQL** instance. Do **not** run MySQL in a container inside Elastic Beanstalk for production workloads.

### Deployment Steps:

1. **Create an Amazon RDS MySQL Database:**
   - Note the endpoint (e.g. `devops-db.c7x...rds.amazonaws.com`), port (`3306`), username, and password.
   - Ensure the RDS Security Group allows inbound traffic on port 3306 from your Elastic Beanstalk environment.

2. **Configure Environment Variables in Elastic Beanstalk:**
   In the AWS Management Console → **Elastic Beanstalk** → **Configuration** → **Software (Environment properties)**, set:
   - `MYSQL_HOST`: `<your-rds-endpoint>`
   - `MYSQL_PORT`: `3306`
   - `MYSQL_DB`: `devops_dashboard`
   - `MYSQL_USER`: `<your-rds-username>`
   - `MYSQL_PASSWORD`: `<your-rds-password>`
   - `SECRET_KEY`: `<a-strong-random-secret>`
   - `PORT`: `5000`

3. **Deploy the Code:**
   - Package the repository into a `.zip` archive (containing `Dockerfile`, `app.py`, `requirements.txt`, `templates/`, `static/`).
   - Upload and deploy to Elastic Beanstalk via the AWS Console or EB CLI (`eb deploy`).
   - The root `Dockerfile` automatically builds and starts Gunicorn binding to `0.0.0.0:5000`.

4. **Health Check Path:**
   - Elastic Beanstalk health check path can be set to `/health` or `/`.

---

## 9. Troubleshooting

### 1. Database Connection Refused
- In Docker Compose, ensure the `database` service has completed initialization. The app automatically retries connecting.
- Check logs: `docker compose logs -f`

### 2. Port 5000 Conflict
- If port 5000 is occupied on your host, adjust `docker-compose.yml`:
  ```yaml
  ports:
    - "5001:5000"
  ```
- Then open [http://localhost:5001](http://localhost:5001).

### 3. Reset Database from Scratch
```bash
docker compose down -v
docker compose up --build
```
