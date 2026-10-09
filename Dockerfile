FROM python:3.12-slim

# Prevent Python bytecode generation and ensure unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=5000

WORKDIR /app

# Install MariaDB (MySQL-compatible server and client) along with procps for process monitoring
RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends \
        mariadb-server \
        mariadb-client \
        procps && \
    rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application assets, database scripts, and supervisor entrypoint
COPY . .
RUN chmod +x entrypoint.sh

# Expose application port (Elastic Beanstalk routes traffic to the single exposed port)
EXPOSE 5000

# Volume for optional data persistence
VOLUME /var/lib/mysql

# Run through the supervisor entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]
