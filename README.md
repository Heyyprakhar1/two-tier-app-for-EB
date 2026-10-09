# DevOps Deployment Dashboard — One ZIP, Two Elastic Beanstalk Modes

A simple, beginner-friendly **two-tier web application** (Python Flask + MySQL) designed to deploy reproducibly using the **exact same source ZIP bundle** across both AWS Elastic Beanstalk deployment modes:

1. **Elastic Beanstalk Standard Mode** (EC2 Single-Container Docker)
2. **Elastic Beanstalk Cluster Mode** (Managed EKS Container Platform)

No RDS configuration, no separate database provisioning, no ECR push steps, and no manual environment variables are required for the learner.

---

## 1. Architecture Overview

### Tutorial Architecture: Zero-Config Embedded MySQL in Container

```text
                               ┌──────────────────────────────────────────────────────────┐
                               │                 Single Docker Container                  │
                               │                                                          │
Browser ──▶ Port 5000 (HTTP) ──┼──▶ Flask Application (Gunicorn WSGI)                     │
                               │           │                                              │
                               │           ▼ (Port 3306 / 127.0.0.1)                      │
                               │     Embedded MySQL (MariaDB 11.x)                        │
                               │     - Automatic schema init via database/init.sql        │
                               │     - Supervised with fail-fast health monitoring        │
                               └──────────────────────────────────────────────────────────┘
```

- **Application Layer:** Flask 3.x with Jinja2 server-rendered dashboard, PyMySQL driver, and Gunicorn WSGI running on port `5000`.
- **Database Layer:** Embedded MySQL-compatible daemon (MariaDB) running on `127.0.0.1:3306`.
- **Process Supervisor:** [entrypoint.sh](file:///home/prakhar/multi-tier-app-for-EB/entrypoint.sh) starts MariaDB, verifies health, seeds demo records from `database/init.sql`, launches Gunicorn, and monitors both processes. If either service dies, the container exits with an error so Elastic Beanstalk detects the failure visibly.
- **External RDS Support:** If an external `MYSQL_HOST` is supplied, the container skips starting the embedded MySQL daemon and connects to the specified remote host.

---

## 2. Why One ZIP Works in Both Elastic Beanstalk Modes

| Consideration | Standard Mode (EC2) | Cluster Mode (EKS) |
|---|---|---|
| **Underlying Compute** | Dedicated Amazon EC2 instances | Managed Amazon EKS (EKS Auto Mode) |
| **Build Mechanism** | Builds `Dockerfile` on EC2 host | Builds `Dockerfile` via AWS CodeBuild & pushes to ECR |
| **Docker Compose Support** | Supported via AL2023 Compose mode | **Not Supported** (Cluster mode builds Dockerfile only) |
| **Database Connectivity** | Connects to `127.0.0.1:3306` inside container | Connects to `127.0.0.1:3306` inside pod container |
| **Learner Effort** | Upload ZIP & click Create | Upload ZIP & click Create |
| **Persistence Behavior** | Persists during runtime; resets on EC2 replacement | Persists during runtime; ephemeral per Pod replica |

---

## 3. Local Development

### Run Locally with Docker Compose

```bash
docker compose up -d --build
```

- **Dashboard:** [http://localhost:5000](http://localhost:5000)
- **Health Check:** [http://localhost:5000/health](http://localhost:5000/health)
- **Deployments API:** [http://localhost:5000/api/deployments](http://localhost:5000/api/deployments)
- **Stats API:** [http://localhost:5000/api/stats](http://localhost:5000/api/stats)

Data is persisted locally in the Docker named volume `mysql_data`.

To stop the application:
```bash
docker compose down
```

To reset the database cleanly:
```bash
docker compose down -v
docker compose up -d --build
```

---

## 4. Packaging the Source Bundle (One ZIP)

Run this exact command from the repository root:

```bash
zip -r eb-deployment.zip . -x ".git/*" ".git" ".venv/*" ".venv" "*__pycache__*" "*.pyc" "*.log" "eb-deployment.zip"
```

### Bundle Structure Verification

Ensure the [Dockerfile](file:///home/prakhar/multi-tier-app-for-EB/Dockerfile) is at the archive root:

```text
eb-deployment.zip
├── Dockerfile              # Root Dockerfile (MariaDB + Flask + Gunicorn on 5000)
├── entrypoint.sh           # Supervisor entrypoint script
├── app.py                  # Flask routes, CRUD handlers, and /health
├── requirements.txt        # Python dependencies
├── docker-compose.yml      # Local dev configuration
├── .dockerignore           # Build exclusions
├── .env.example            # Environment reference
├── .gitignore              # Git ignore rules
├── database/
│   └── init.sql            # Table schema & initial demonstration records
├── templates/
│   └── index.html          # Server-rendered dashboard HTML
└── static/
    └── style.css           # Clean CSS styles
```

---

## 5. Elastic Beanstalk Deployment Steps

### Mode A: Elastic Beanstalk Standard Mode (Traditional EC2)

1. Open the **AWS Elastic Beanstalk Console**.
2. Click **Create Application** (or **Create environment**).
3. **Environment tier:** Select **Web server environment**.
4. **Platform:** Select **Docker** (Platform branch: *Docker running on 64bit Amazon Linux 2023*).
5. **Application code:**
   - Choose **Upload your code**.
   - Select **Local file** and upload `eb-deployment.zip`.
6. Click **Create environment**.
7. Elastic Beanstalk provisions an EC2 instance, builds the `Dockerfile`, launches the container, routes port 80 to port 5000, and verifies `/health`.

---

### Mode B: Elastic Beanstalk Cluster Mode (Managed EKS)

1. Open the **AWS Elastic Beanstalk Console**.
2. Click **Create application** (or **Create environment**).
3. **Environment mode:** Select **Cluster Mode** (Managed infrastructure on EKS).
4. **Application code:**
   - Choose **Upload your code**.
   - Select **Local file** and upload the exact same `eb-deployment.zip`.
5. Click **Create environment**.
6. Elastic Beanstalk triggers AWS CodeBuild to build the image from `Dockerfile`, pushes it to ECR, schedules the pod on EKS Auto Mode, configures ingress to port 5000, and verifies `/health`.

---

## 6. Trade-Offs and Architectural Notes

1. **Tutorial vs. Production Storage:**
   - **Tutorial Mode:** Embedding MySQL in the container allows zero-cost, zero-configuration deployment in both EB modes with one ZIP.
   - **Production Mode:** For durable production workloads, databases must run externally (e.g., **Amazon RDS**) to ensure persistence across container rollouts, auto-scaling, and cluster node replacements.
2. **Process Supervision:**
   - [entrypoint.sh](file:///home/prakhar/multi-tier-app-for-EB/entrypoint.sh) acts as a lightweight supervisor monitoring both MariaDB and Gunicorn. If either crashes, the container exits with a non-zero code to ensure failure is immediately visible in Elastic Beanstalk health metrics.
