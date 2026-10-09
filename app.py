import os
import time
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import pymysql
import pymysql.cursors

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("deployment-dashboard")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

# MySQL Database configuration with environment variables
MYSQL_HOST = os.getenv("MYSQL_HOST", os.getenv("DB_HOST", "127.0.0.1"))
MYSQL_PORT = int(os.getenv("MYSQL_PORT", os.getenv("DB_PORT", "3306")))
MYSQL_USER = os.getenv("MYSQL_USER", os.getenv("DB_USER", "dashboard"))
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", os.getenv("DB_PASSWORD", "dashboard123"))
MYSQL_DB = os.getenv("MYSQL_DB", os.getenv("DB_NAME", "devops_dashboard"))

VALID_STATUSES = {"SUCCESS", "FAILED", "IN_PROGRESS"}
VALID_ENVIRONMENTS = {"production", "staging", "development", "qa"}


def get_db_connection(max_retries=5, retry_delay=2):
    """
    Establish database connection with retry logic to withstand container
    startup timing or transient network delays.
    """
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            connection = pymysql.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DB,
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True,
                connect_timeout=5
            )
            return connection
        except pymysql.MySQLError as err:
            last_error = err
            logger.warning(
                "Database connection attempt %d/%d failed: %s. Retrying in %ds...",
                attempt, max_retries, err, retry_delay
            )
            time.sleep(retry_delay)

    logger.error("All %d database connection attempts failed: %s", max_retries, last_error)
    raise last_error


def init_db(max_retries=10, retry_delay=2):
    """
    Ensures table schema exists upon startup.
    Works seamlessly both with local MySQL container and external Amazon RDS.
    """
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            conn = pymysql.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DB,
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True,
                connect_timeout=5
            )
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS deployments (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        application VARCHAR(100) NOT NULL,
                        version VARCHAR(50) NOT NULL,
                        environment VARCHAR(50) NOT NULL,
                        status ENUM('SUCCESS', 'FAILED', 'IN_PROGRESS') NOT NULL DEFAULT 'IN_PROGRESS',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
            conn.close()
            logger.info("Database schema verified.")
            return True
        except pymysql.MySQLError as err:
            last_error = err
            logger.warning(
                "Database init attempt %d/%d failed: %s. Retrying in %ds...",
                attempt, max_retries, err, retry_delay
            )
            time.sleep(retry_delay)

    logger.warning("Database init could not complete: %s", last_error)
    return False


# Attempt eager initialization once on startup without blocking
try:
    init_db(max_retries=1, retry_delay=0)
except Exception:
    pass


@app.template_filter("format_datetime")
def format_datetime(value):
    """Format MySQL timestamp cleanly for presentation."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value) if value else "N/A"


@app.route("/")
def index():
    deployments = []
    stats = {
        "total": 0,
        "successful": 0,
        "failed": 0,
        "in_progress": 0
    }
    db_connected = False

    try:
        conn = get_db_connection(max_retries=3, retry_delay=1)
        with conn.cursor() as cursor:
            # Aggregate deployment statistics
            cursor.execute("""
                SELECT
                    COUNT(*) AS total,
                    COALESCE(SUM(status = 'SUCCESS'), 0) AS successful,
                    COALESCE(SUM(status = 'FAILED'), 0) AS failed,
                    COALESCE(SUM(status = 'IN_PROGRESS'), 0) AS in_progress
                FROM deployments;
            """)
            stats_row = cursor.fetchone()
            if stats_row:
                stats = {
                    "total": int(stats_row["total"] or 0),
                    "successful": int(stats_row["successful"] or 0),
                    "failed": int(stats_row["failed"] or 0),
                    "in_progress": int(stats_row["in_progress"] or 0)
                }

            # Fetch deployments ordered by newest first
            cursor.execute("""
                SELECT id, application, version, environment, status, created_at
                FROM deployments
                ORDER BY created_at DESC, id DESC;
            """)
            deployments = cursor.fetchall()
            db_connected = True
        conn.close()
    except Exception as err:
        logger.error("Error fetching dashboard data: %s", err)
        flash("Could not connect to database. Please check database connection and settings.", "error")

    return render_template(
        "index.html",
        deployments=deployments,
        stats=stats,
        db_connected=db_connected
    )


@app.route("/deployments", methods=["POST"])
def create_deployment():
    application = (request.form.get("application") or "").strip()
    version = (request.form.get("version") or "").strip()
    environment = (request.form.get("environment") or "").strip().lower()
    status = (request.form.get("status") or "").strip().upper()

    # Validation
    errors = []
    if not application:
        errors.append("Application name is required.")
    elif len(application) > 100:
        errors.append("Application name cannot exceed 100 characters.")

    if not version:
        errors.append("Version is required.")
    elif len(version) > 50:
        errors.append("Version cannot exceed 50 characters.")

    if not environment:
        errors.append("Environment is required.")
    elif len(environment) > 50:
        errors.append("Environment cannot exceed 50 characters.")

    if status not in VALID_STATUSES:
        errors.append(f"Invalid status '{status}'. Must be one of: SUCCESS, FAILED, IN_PROGRESS.")

    if errors:
        for err in errors:
            flash(err, "error")
        return redirect(url_for("index"))

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO deployments (application, version, environment, status)
                VALUES (%s, %s, %s, %s);
            """, (application, version, environment, status))
        conn.close()
        flash(f"Deployment record for '{application}' ({version}) successfully created!", "success")
    except Exception as err:
        logger.error("Failed to insert deployment: %s", err)
        flash("Database error: unable to save deployment record.", "error")

    return redirect(url_for("index"))


@app.route("/deployments/<int:deployment_id>/delete", methods=["POST"])
def delete_deployment(deployment_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM deployments WHERE id = %s;", (deployment_id,))
            affected = cursor.rowcount
        conn.close()

        if affected > 0:
            flash(f"Deployment #{deployment_id} deleted successfully.", "success")
        else:
            flash(f"Deployment #{deployment_id} not found.", "error")
    except Exception as err:
        logger.error("Failed to delete deployment %s: %s", deployment_id, err)
        flash("Database error: unable to delete deployment record.", "error")

    return redirect(url_for("index"))


@app.route("/health")
def health():
    """
    Lightweight health check endpoint.
    Verifies that the Flask app is responding and can query the database,
    without exposing any database credentials or internal topology.
    """
    try:
        conn = get_db_connection(max_retries=1, retry_delay=0)
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1;")
        conn.close()
        return jsonify({
            "status": "healthy",
            "database": "connected"
        }), 200
    except Exception as err:
        logger.warning("Health check DB probe failed: %s", err)
        return jsonify({
            "status": "degraded",
            "database": "disconnected"
        }), 503


@app.route("/api/deployments", methods=["GET"])
def api_deployments():
    """Read-only JSON endpoint for deployment records."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, application, version, environment, status, created_at
                FROM deployments
                ORDER BY created_at DESC, id DESC;
            """)
            records = cursor.fetchall()
            for r in records:
                if isinstance(r.get("created_at"), datetime):
                    r["created_at"] = r["created_at"].isoformat()
        conn.close()
        return jsonify(records), 200
    except Exception as err:
        logger.error("API error fetching deployments: %s", err)
        return jsonify({"error": "Failed to query database"}), 500


@app.route("/api/stats", methods=["GET"])
def api_stats():
    """Read-only JSON endpoint for deployment statistics."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    COUNT(*) AS total,
                    COALESCE(SUM(status = 'SUCCESS'), 0) AS successful,
                    COALESCE(SUM(status = 'FAILED'), 0) AS failed,
                    COALESCE(SUM(status = 'IN_PROGRESS'), 0) AS in_progress
                FROM deployments;
            """)
            row = cursor.fetchone()
        conn.close()
        return jsonify({
            "total": int(row["total"] or 0),
            "successful": int(row["successful"] or 0),
            "failed": int(row["failed"] or 0),
            "in_progress": int(row["in_progress"] or 0)
        }), 200
    except Exception as err:
        logger.error("API error fetching stats: %s", err)
        return jsonify({"error": "Failed to query database"}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
