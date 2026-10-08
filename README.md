# DevOps Deployment Dashboard

A small three-tier demo application built to demonstrate a real application flow through Docker Compose and AWS Elastic Beanstalk.

## Architecture

Browser → Nginx Frontend → FastAPI Backend → MySQL

## Features

- Live deployment dashboard
- Deployment statistics
- Add and delete deployment records
- MySQL-backed persistent application data
- REST API with FastAPI
- Nginx reverse proxy
- Docker Compose for local development

## Run locally

```bash
docker compose up --build
```

Open http://localhost:8080.

This project is intentionally small. The application demonstrates the multi-tier flow without adding authentication, queues, caches, or external services.
