from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import json
import datetime
from src.graph import run_agent_workflow
from src.mailer import send_email
from src.config import DATA_DIR, logger, validate_config

app = FastAPI(title="UPSC Agentic Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RunStatus(BaseModel):
    is_running: bool
    status_message: str

class EmailRequest(BaseModel):
    html_content: str

# Global state to track running status
agent_state = {
    "is_running": False,
    "status_message": "Idle",
    "last_run_state": None
}

def execute_agent_background():
    global agent_state
    try:
        if not validate_config():
            agent_state["status_message"] = "Configuration invalid. Check .env file."
            agent_state["is_running"] = False
            return
            
        logger.info("Starting background agent run...")
        agent_state["status_message"] = "Agent workflow running..."
        
        final_state = run_agent_workflow()
        
        agent_state["last_run_state"] = final_state
        agent_state["status_message"] = "Workflow completed successfully."
        
        # Save cache
        if final_state.get("generated_cards"):
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            cache_file = os.path.join(DATA_DIR, f"brief_{date_str}.json")
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(final_state["generated_cards"], f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Failed to save cache: {e}")
                
    except Exception as e:
        logger.error(f"Error in agent run: {e}")
        agent_state["status_message"] = f"Error: {str(e)}"
    finally:
        agent_state["is_running"] = False

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
        raise HTTPException(status_code=400, detail="Agent is already running.")
        
    agent_state["is_running"] = True
    agent_state["status_message"] = "Initializing..."
    background_tasks.add_task(execute_agent_background)
    return {"message": "Agent workflow triggered."}

@app.get("/api/latest-cards")
def get_latest_cards():
    global agent_state
    # If we just ran it, return from memory
    if agent_state["last_run_state"] and agent_state["last_run_state"].get("generated_cards"):
        return {
            "cards": agent_state["last_run_state"]["generated_cards"],
            "html": agent_state["last_run_state"].get("final_html", "")
        }
        
    # Otherwise check today's cache
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    cache_file = os.path.join(DATA_DIR, f"brief_{date_str}.json")
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cards = json.load(f)
            from src.mailer import build_newsletter_html
            html = build_newsletter_html(cards)
            return {"cards": cards, "html": html}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading cache: {e}")
            
    return {"cards": [], "html": ""}

@app.post("/api/approve")
def approve_and_send(req: EmailRequest):
    date_str = datetime.datetime.now().strftime("%d %b %Y")
    subject = f"UPSC Daily Brief - {date_str}"
    
    success = send_email(subject, req.html_content)
    if success:
        return {"message": "Email sent successfully!"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send email. Check logs.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
