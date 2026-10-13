from fastapi import FastAPI, BackgroundTasks, HTTPException, Header, Query, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import os
import glob
import json
import datetime
from src.graph import run_agent_workflow
from src.mailer import send_email, build_newsletter_html
from src.config import DATA_DIR, logger, validate_config
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
    get_overview_stats
)

app = FastAPI(title="UPSC Agentic Weekly Intelligence API")

# Ensure database is initialized
init_db()

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

# Global state to track background agent execution
agent_state = {
    "is_running": False,
    "status_message": "Idle",
    "last_run_state": None
}

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
