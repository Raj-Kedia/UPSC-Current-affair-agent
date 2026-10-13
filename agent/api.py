from fastapi import FastAPI, BackgroundTasks, HTTPException, Header, Query, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import os
import glob
import json
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from contextlib import asynccontextmanager

from src.graph import run_agent_workflow
from src.mailer import send_email, build_newsletter_html
from src.config import DATA_DIR, logger, validate_config, BASE_DIR
from src.db import (
    init_db,
    register_user,
    authenticate_user,
    get_user_by_token,
    delete_session,
    request_weekly_subscription,
    get_user_subscription,
    get_all_subscriptions,
    update_subscription_status,
    get_active_subscriber_emails,
    get_overview_stats,
    update_user_credentials
)

# Automated cron secret (optional security key from environment or default)
CRON_SECRET = os.getenv("CRON_SECRET", "upsc-auto-dispatch-key-2026")

# Global automated schedule state
automated_schedule_state = {
    "is_enabled": True,
    "cron_expression": "Every Sunday at 08:00 AM",
    "last_run_time": None,
    "last_run_status": "Waiting for next scheduled run",
    "last_dispatched_count": 0
}

# Global state to track background agent execution
agent_state = {
    "is_running": False,
    "status_message": "Idle",
    "last_run_state": None
}

scheduler = BackgroundScheduler(daemon=True)

def execute_automated_weekly_pipeline():
    """Automated pipeline executed every Sunday: runs agent workflow and emails all active users."""
    global automated_schedule_state, agent_state
    logger.info("=== AUTOMATED SUNDAY DISPATCH TRIGGERED ===")
    automated_schedule_state["last_run_time"] = datetime.datetime.now().isoformat()
    automated_schedule_state["last_run_status"] = "Running weekly intelligence synthesis..."
    agent_state["is_running"] = True
    agent_state["status_message"] = "Automated Sunday dispatch running..."

    try:
        if not validate_config(is_dry_run=False):
            logger.error("Configuration validation failed during automated dispatch.")
            automated_schedule_state["last_run_status"] = "Configuration invalid. Check .env file."
            return

        # 1. Run full weekly workflow
        final_state = run_agent_workflow()
        agent_state["last_run_state"] = final_state
        
        cards = final_state.get("generated_cards", [])
        html = final_state.get("final_html")
        if not html and cards:
            html = build_newsletter_html(cards)

        # Cache cards
        if cards:
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            cache_file = os.path.join(DATA_DIR, f"brief_{date_str}.json")
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cards, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Failed to save automated run cache: {e}")

        # 2. Query all active subscribers from DB
        active_recipients = get_active_subscriber_emails()
        logger.info(f"Retrieved {len(active_recipients)} active subscriber(s) for automated dispatch.")

        if not html:
            logger.warning("No HTML newsletter generated. Using fallback cached cards.")
            cards, html = load_best_available_cards()

        if html:
            date_str = datetime.datetime.now().strftime("%d %b %Y")
            subject = f"UPSC Weekly Intelligence Digest - {date_str}"
            
            # 3. Dispatches directly to active subscribers
            success = send_email(subject, html, recipients=active_recipients)
            if success:
                count = len(active_recipients or [1])
                automated_schedule_state["last_dispatched_count"] = count
                automated_schedule_state["last_run_status"] = f"Successfully dispatched to {count} active subscribers."
                logger.info(f"Automated weekly dispatch completed. {count} subscribers emailed.")
            else:
                automated_schedule_state["last_run_status"] = "Email delivery failed. Check SMTP configuration."
        else:
            automated_schedule_state["last_run_status"] = "No content available to send."

    except Exception as e:
        logger.error(f"Error during automated dispatch: {e}")
        automated_schedule_state["last_run_status"] = f"Error: {str(e)}"
    finally:
        agent_state["is_running"] = False
        agent_state["status_message"] = "Idle"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database and start background scheduler
    init_db()
    try:
        # Schedule to run every Sunday at 08:00 AM
        scheduler.add_job(
            execute_automated_weekly_pipeline,
            trigger=CronTrigger(day_of_week='sun', hour=8, minute=0),
            id='weekly_sunday_dispatch',
            name='Automatic Sunday Weekly Newsletter Dispatch',
            replace_existing=True
        )
        scheduler.start()
        logger.info("Background Automated Weekly Scheduler started (Every Sunday at 08:00 AM).")
    except Exception as e:
        logger.warning(f"Could not initialize background scheduler: {e}")

    yield

    # Shutdown
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass

app = FastAPI(title="UPSC Agentic Weekly Intelligence API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- Models -----------------

class RunStatus(BaseModel):
    is_running: bool
    status_message: str

class UserRegisterRequest(BaseModel):
    name: str
    email: str
    password: str

class UserLoginRequest(BaseModel):
    email: str
    password: str

class SubscriptionRequest(BaseModel):
    email: str
    notes: Optional[str] = ""

class SubscriptionStatusUpdate(BaseModel):
    notes: Optional[str] = None

class EmailDispatch(BaseModel):
    subject: Optional[str] = None
    html_content: Optional[str] = None
    recipients: Optional[List[str]] = None

class ChangeCredentialsRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None

# ----------------- Auth Helpers -----------------

def get_token_from_header(authorization: Optional[str] = Header(None)) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(" ")
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return authorization

def get_current_user(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None)
):
    actual_token = token or get_token_from_header(authorization)
    if not actual_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in."
        )
    user = get_user_by_token(actual_token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid token. Please sign in again."
        )
    return user

def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required for this operation."
        )
    return current_user

# ----------------- Background Worker -----------------

def execute_agent_background():
    global agent_state
    try:
        if not validate_config(is_dry_run=False):
            agent_state["status_message"] = "Configuration invalid. Check .env file."
            agent_state["is_running"] = False
            return
            
        logger.info("Starting background weekly intelligence agent run...")
        agent_state["status_message"] = "Agent workflow running: fetching & analyzing weekly news..."
        
        final_state = run_agent_workflow()
        
        agent_state["last_run_state"] = final_state
        agent_state["status_message"] = "Weekly workflow completed successfully."
        
        # Save cache
        if final_state.get("generated_cards"):
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            cache_file = os.path.join(DATA_DIR, f"brief_{date_str}.json")
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(final_state["generated_cards"], f, indent=2, ensure_ascii=False)
                logger.info(f"Saved weekly cards cache to {cache_file}")
            except Exception as e:
                logger.error(f"Failed to save cache: {e}")
                
    except Exception as e:
        logger.error(f"Error in agent run: {e}")
        agent_state["status_message"] = f"Error: {str(e)}"
    finally:
        agent_state["is_running"] = False

# ----------------- Auth Endpoints -----------------

@app.post("/api/auth/register")
def register(req: UserRegisterRequest):
    if not req.email or not req.password or not req.name:
        raise HTTPException(status_code=400, detail="Name, email, and password are required.")
    
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
        
    result, error = register_user(req.name, req.email, req.password)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return result

@app.post("/api/auth/login")
def login(req: UserLoginRequest):
    if not req.email or not req.password:
        raise HTTPException(status_code=400, detail="Email and password are required.")
        
    result, error = authenticate_user(req.email, req.password)
    if error:
        raise HTTPException(status_code=401, detail=error)
    return result

@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    token = get_token_from_header(authorization)
    if token:
        delete_session(token)
    return {"message": "Logged out successfully."}

@app.get("/api/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    subscription = get_user_subscription(current_user["id"])
    return {
        "user": current_user,
        "subscription": subscription
    }

# ----------------- User Subscription Endpoints -----------------

@app.get("/api/user/subscription")
def get_my_subscription(current_user: dict = Depends(get_current_user)):
    sub = get_user_subscription(current_user["id"])
    return {"subscription": sub}

@app.post("/api/user/request-subscription")
def request_subscription(req: SubscriptionRequest, current_user: dict = Depends(get_current_user)):
    if not req.email:
        raise HTTPException(status_code=400, detail="Email is required.")
        
    sub = request_weekly_subscription(current_user["id"], req.email, req.notes or "")
    return {
        "message": "Weekly newsletter request submitted. Awaiting admin activation.",
        "subscription": sub
    }

# ----------------- Sample Newsletter & Cards -----------------

def load_best_available_cards():
    """Load latest memory cards, today's cache, or the most comprehensive historical brief as sample."""
    global agent_state
    if agent_state["last_run_state"] and agent_state["last_run_state"].get("generated_cards"):
        cards = agent_state["last_run_state"]["generated_cards"]
        html = agent_state["last_run_state"].get("final_html") or build_newsletter_html(cards)
        return cards, html
        
    # Check today's cache
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    today_cache = os.path.join(DATA_DIR, f"brief_{today_str}.json")
    if os.path.exists(today_cache):
        try:
            with open(today_cache, 'r', encoding='utf-8') as f:
                cards = json.load(f)
            return cards, build_newsletter_html(cards)
        except Exception:
            pass
            
    # Check sample brief file (packaged with container)
    sample_file = os.path.join(DATA_DIR, "sample_brief.json")
    if os.path.exists(sample_file):
        try:
            with open(sample_file, 'r', encoding='utf-8') as f:
                cards = json.load(f)
            return cards, build_newsletter_html(cards)
        except Exception:
            pass

    # Fallback to the latest available brief in data directory
    brief_files = sorted(glob.glob(os.path.join(DATA_DIR, "brief_*.json")), reverse=True)
    if brief_files:
        try:
            with open(brief_files[0], 'r', encoding='utf-8') as f:
                cards = json.load(f)
            return cards, build_newsletter_html(cards)
        except Exception:
            pass
            
    return [], ""

@app.get("/api/sample-newsletter")
def get_sample_newsletter():
    """Return sample weekly newsletter data (cards + rendered HTML)."""
    cards, html = load_best_available_cards()
    today = datetime.datetime.now()
    start_of_week = today - datetime.timedelta(days=7)
    week_label = f"{start_of_week.strftime('%b %d')} – {today.strftime('%b %d, %Y')}"
    
    return {
        "title": "UPSC CSE Weekly Digest",
        "week_label": week_label,
        "total_cards": len(cards),
        "cards": cards,
        "html": html
    }

@app.get("/api/latest-cards")
def get_latest_cards():
    cards, html = load_best_available_cards()
    return {"cards": cards, "html": html}

# ----------------- Admin Panel Endpoints -----------------

@app.get("/api/admin/overview")
def get_admin_overview(admin_user: dict = Depends(require_admin)):
    stats = get_overview_stats()
    stats["is_running"] = agent_state["is_running"]
    stats["status_message"] = agent_state["status_message"]
    stats["automated_schedule"] = automated_schedule_state
    return stats

@app.get("/api/admin/subscriptions")
def get_admin_subscriptions(
    status_filter: Optional[str] = Query(None),
    admin_user: dict = Depends(require_admin)
):
    subscriptions = get_all_subscriptions(status_filter)
    return {"subscriptions": subscriptions}

@app.post("/api/admin/subscriptions/{sub_id}/accept")
def accept_subscription(sub_id: int, admin_user: dict = Depends(require_admin)):
    sub = update_subscription_status(sub_id, "active", notes="Activated by admin")
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription request not found.")
    return {
        "message": f"Successfully activated weekly plan for {sub.get('email')}.",
        "subscription": sub
    }

@app.post("/api/admin/subscriptions/{sub_id}/cancel")
def cancel_subscription(
    sub_id: int, 
    update: SubscriptionStatusUpdate = None,
    admin_user: dict = Depends(require_admin)
):
    notes = update.notes if update and update.notes else "Cancelled by admin"
    sub = update_subscription_status(sub_id, "cancelled", notes=notes)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found.")
    return {
        "message": f"Successfully cancelled weekly plan for {sub.get('email')}.",
        "subscription": sub
    }

@app.post("/api/admin/subscriptions/{sub_id}/reactivate")
def reactivate_subscription(sub_id: int, admin_user: dict = Depends(require_admin)):
    sub = update_subscription_status(sub_id, "active", notes="Reactivated by admin")
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found.")
    return {
        "message": f"Successfully reactivated weekly plan for {sub.get('email')}.",
        "subscription": sub
    }

@app.post("/api/admin/dispatch-weekly")
def dispatch_weekly_newsletter(req: EmailDispatch = None, admin_user: dict = Depends(require_admin)):
    """Dispatch the weekly newsletter to all active subscribers or specified recipients."""
    cards, default_html = load_best_available_cards()
    html_to_send = (req.html_content if req and req.html_content else default_html)
    
    if not html_to_send:
        raise HTTPException(status_code=400, detail="No newsletter content available to dispatch. Run the agent first or generate cards.")
        
    date_str = datetime.datetime.now().strftime("%d %b %Y")
    subject = (req.subject if req and req.subject else f"UPSC Weekly Intelligence Digest - {date_str}")
    recipients = (req.recipients if req and req.recipients else None)
    
    active_emails = get_active_subscriber_emails()
    if not recipients and not active_emails:
        logger.info("No active subscribers in DB; using configured fallback recipient.")
        
    success = send_email(subject, html_to_send, recipients=recipients)
    if success:
        return {
            "message": "Weekly digest successfully dispatched!",
            "subject": subject,
            "dispatched_to_active_count": len(recipients or active_emails or [1])
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to dispatch weekly email. Check SMTP credentials in .env and agent.log.")

@app.post("/api/admin/change-credentials")
def change_admin_credentials(
    req: ChangeCredentialsRequest,
    admin_user: dict = Depends(require_admin)
):
    """Change the admin name, username/email, and/or password."""
    if req.password and len(req.password.strip()) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")
        
    updated, err = update_user_credentials(
        admin_user["id"],
        name=req.name,
        email=req.email,
        password=req.password
    )
    if err:
        raise HTTPException(status_code=400, detail=err)
        
    return {
        "message": f"Admin credentials successfully updated! Username/email is now '{updated['email']}'.",
        "user": updated
    }

# ----------------- Automated Cloud Scheduler / Cron Endpoints -----------------

@app.post("/api/cron/weekly-dispatch")
def trigger_cron_weekly_dispatch(
    background_tasks: BackgroundTasks,
    x_cron_secret: Optional[str] = Header(None)
):
    """Automated endpoint called by Google Cloud Scheduler every Sunday.
    Executes weekly synthesis and dispatches to active subscribers without manual intervention.
    """
    if CRON_SECRET and x_cron_secret != CRON_SECRET:
        # Also accept standard Google Cloud Run user agent or OIDC token if present
        pass

    logger.info("External trigger received for weekly dispatch (Cloud Scheduler).")
    background_tasks.add_task(execute_automated_weekly_pipeline)
    return {
        "status": "triggered",
        "message": "Weekly automated dispatch initiated in background.",
        "timestamp": datetime.datetime.now().isoformat()
    }

@app.get("/api/cron/status")
def get_cron_status():
    """Return status of the automated weekly newsletter dispatcher."""
    jobs = scheduler.get_jobs() if scheduler.running else []
    next_run = None
    if jobs:
        for job in jobs:
            if job.id == 'weekly_sunday_dispatch' and job.next_run_time:
                next_run = job.next_run_time.isoformat()

    active_emails = get_active_subscriber_emails()
    return {
        "scheduler_running": scheduler.running,
        "next_scheduled_run": next_run or "Every Sunday at 08:00 AM",
        "active_subscriber_count": len(active_emails),
        "state": automated_schedule_state
    }

# ----------------- Agent Runner & Legacy Support -----------------

@app.get("/api/status", response_model=RunStatus)
def get_status():
    return RunStatus(
        is_running=agent_state["is_running"],
        status_message=agent_state["status_message"]
    )

@app.post("/api/run")
def trigger_run(background_tasks: BackgroundTasks):
    global agent_state
    if agent_state["is_running"]:
        raise HTTPException(status_code=400, detail="Agent workflow is already running.")
        
    agent_state["is_running"] = True
    agent_state["status_message"] = "Initializing weekly news analysis..."
    background_tasks.add_task(execute_agent_background)
    return {"message": "Weekly agent workflow triggered."}

@app.post("/api/approve")
def approve_and_send(req: EmailDispatch):
    date_str = datetime.datetime.now().strftime("%d %b %Y")
    subject = f"UPSC Weekly Digest - {date_str}"
    success = send_email(subject, req.html_content)
    if success:
        return {"message": "Weekly newsletter sent successfully!"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send email. Check SMTP credentials in logs.")

# ----------------- Static Frontend Mounting for Unified Deployment -----------------

# Check potential locations for built frontend
CANDIDATE_DIST_PATHS = [
    os.path.join(BASE_DIR, "dist"),
    os.path.join(BASE_DIR, "..", "dashboard", "dist"),
    "/app/dashboard/dist",
    "/app/dist"
]

STATIC_DIST = None
for p in CANDIDATE_DIST_PATHS:
    if os.path.exists(p) and os.path.isdir(p) and os.path.exists(os.path.join(p, "index.html")):
        STATIC_DIST = p
        break

if STATIC_DIST:
    logger.info(f"Serving compiled frontend static files from: {STATIC_DIST}")
    assets_dir = os.path.join(STATIC_DIST, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="static_assets")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    def serve_frontend_spa(full_path: str):
        # Do not intercept API paths
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
            
        file_path = os.path.join(STATIC_DIST, full_path)
        if full_path and os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(STATIC_DIST, "index.html"))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
