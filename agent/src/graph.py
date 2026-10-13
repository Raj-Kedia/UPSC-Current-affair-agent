import os
from typing import Dict, TypedDict, Any, List
import concurrent.futures
from langgraph.graph import StateGraph, END
from src.fetcher import fetch_all_recent_news, fetch_verification_data
from src.analyzer import curate_news_with_verification, analyze_article, evaluate_and_refine_card
from src.mailer import build_newsletter_html, send_email
from src.config import logger

class AgentState(TypedDict):
    """The state of the UPSC Agent Workflow."""
    raw_articles: List[Dict[str, Any]]
    verification_data: Dict[str, Any]
    curated_articles: List[Dict[str, Any]]
    generated_cards: List[Dict[str, Any]]
    final_html: str
    email_sent: bool
    status_message: str

def fetch_news_node(state: AgentState):
    """Node: Fetches raw news from various sources for weekly digest (last 7 days)."""
    logger.info("LangGraph Node: fetch_news_node (Weekly cadence, 168 hours)")
    articles = fetch_all_recent_news(max_hours=168)
    return {"raw_articles": articles, "status_message": f"Fetched {len(articles)} raw articles for weekly review."}

def fetch_verification_node(state: AgentState):
    """Node: Fetches verification data (Insights, YouTube)."""
    logger.info("LangGraph Node: fetch_verification_node")
    v_data = fetch_verification_data()
    return {"verification_data": v_data, "status_message": "Fetched verification data."}

def curate_node(state: AgentState):
    """Node: Deduplicates and filters news using verification data."""
    logger.info("LangGraph Node: curate_node")
    articles = state.get("raw_articles", [])
    v_data = state.get("verification_data", {})
    
    curated = curate_news_with_verification(articles, v_data)
    return {"curated_articles": curated, "status_message": f"Curated {len(curated)} articles."}

def process_single_article(article):
    """Pipeline for a single article to run concurrently."""
    card = analyze_article(article)
    refined_card = evaluate_and_refine_card(card)
    
    if refined_card.get('syllabus_topic') in ('GS Paper I/II/III: Current Affairs', '') and article.get('_pre_classified'):
        refined_card['syllabus_topic'] = article['_pre_classified']
        
    return refined_card

def analyze_and_evaluate_node(state: AgentState):
    """Node: Analyzes and evaluates cards concurrently for the curated articles."""
    logger.info("LangGraph Node: analyze_and_evaluate_node (Parallel)")
    curated = state.get("curated_articles", [])
    if not curated:
        return {"generated_cards": [], "status_message": "No curated articles to analyze."}
        
    max_cards = min(5, len(curated))
    
    # Execute LLM calls concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_cards) as executor:
        cards = list(executor.map(process_single_article, curated[:max_cards]))
        
    return {"generated_cards": cards, "status_message": f"Generated {len(cards)} study cards concurrently."}

def newsletter_generator_node(state: AgentState):
    """Node: Generates the HTML newsletter."""
    logger.info("LangGraph Node: newsletter_generator_node")
    cards = state.get("generated_cards", [])
    if not cards:
        return {"final_html": "", "status_message": "No cards available to generate newsletter."}
        
    html = build_newsletter_html(cards)
    return {"final_html": html, "status_message": "Newsletter HTML generated."}

def route_after_curation(state: AgentState):
    """Router: Decides if we should analyze or end based on curated articles."""
    curated = state.get("curated_articles", [])
    if not curated:
        logger.info("Router: No curated articles, skipping to END.")
        return "end"
    logger.info("Router: Found curated articles, proceeding to analysis.")
    return "analyze"

def build_workflow():
    """Builds and compiles the LangGraph state machine."""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("fetch_news", fetch_news_node)
    workflow.add_node("fetch_verification", fetch_verification_node)
    workflow.add_node("curate", curate_node)
    workflow.add_node("analyze_evaluate", analyze_and_evaluate_node)
    workflow.add_node("generate_newsletter", newsletter_generator_node)
    
    # Define edges
    workflow.set_entry_point("fetch_news")
    workflow.add_edge("fetch_news", "fetch_verification")
    workflow.add_edge("fetch_verification", "curate")
    
    # Conditional edge after curation
    workflow.add_conditional_edges(
        "curate",
        route_after_curation,
        {
            "analyze": "analyze_evaluate",
            "end": END
        }
    )
    
    workflow.add_edge("analyze_evaluate", "generate_newsletter")
    workflow.add_edge("generate_newsletter", END)
    
    # Compile
    return workflow.compile()

def run_agent_workflow():
    """Helper function to run the graph and return the final state."""
    app = build_workflow()
    initial_state = {
        "raw_articles": [],
        "verification_data": {},
        "curated_articles": [],
        "generated_cards": [],
        "final_html": "",
        "email_sent": False,
        "status_message": "Starting workflow..."
    }
    
    logger.info("Starting LangGraph orchestrated workflow...")
    final_state = app.invoke(initial_state)
    logger.info("Workflow complete.")
    return final_state
