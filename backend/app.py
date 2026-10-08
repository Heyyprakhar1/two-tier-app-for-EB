import os,time
import mysql.connector
from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app=FastAPI(title="DevOps Deployment Dashboard API",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])

def db():
    last=None
    for _ in range(30):
        try:
            return mysql.connector.connect(host=os.getenv("DB_HOST","database"),port=int(os.getenv("DB_PORT","3306")),user=os.getenv("DB_USER","dashboard"),password=os.getenv("DB_PASSWORD","dashboard123"),database=os.getenv("DB_NAME","devops_dashboard"))
        except mysql.connector.Error as e:
            last=e; time.sleep(2)
    raise last

class Deployment(BaseModel):
    application:str
    version:str
    environment:str
    status:str

@app.get("/api/health")
def health():
    c=db(); c.close(); return {"status":"healthy","database":"connected"}

@app.get("/api/deployments")
def list_deployments():
    c=db(); cur=c.cursor(dictionary=True)
    cur.execute("SELECT id,application,version,environment,status,created_at FROM deployments ORDER BY created_at DESC")
    rows=cur.fetchall(); cur.close(); c.close()
    for r in rows: r["created_at"]=r["created_at"].isoformat()
    return rows

@app.get("/api/stats")
def stats():
    c=db(); cur=c.cursor(dictionary=True)
    cur.execute("SELECT COUNT(*) total,SUM(status='SUCCESS') successful,SUM(status='FAILED') failed,SUM(status='IN_PROGRESS') in_progress FROM deployments")
    r=cur.fetchone(); cur.close(); c.close(); return r

@app.post("/api/deployments",status_code=201)
def create(item:Deployment):
    if item.status not in {"SUCCESS","FAILED","IN_PROGRESS"}: raise HTTPException(400,"Invalid status")
    c=db(); cur=c.cursor()
    cur.execute("INSERT INTO deployments(application,version,environment,status) VALUES(%s,%s,%s,%s)",(item.application,item.version,item.environment,item.status))
    c.commit(); new_id=cur.lastrowid; cur.close(); c.close()
    return {"id":new_id,**item.model_dump()}

@app.delete("/api/deployments/{deployment_id}")
def delete(deployment_id:int):
    c=db(); cur=c.cursor(); cur.execute("DELETE FROM deployments WHERE id=%s",(deployment_id,)); c.commit(); n=cur.rowcount; cur.close(); c.close()
    if not n: raise HTTPException(404,"Deployment not found")
    return {"deleted":deployment_id}
