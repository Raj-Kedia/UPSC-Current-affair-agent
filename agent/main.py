import os
import argparse
import sys
import shutil
import datetime
import json
from src.config import validate_config, logger, BASE_DIR, DATA_DIR, RECEIVER_EMAIL
from src.fetcher import fetch_all_recent_news, fetch_verification_data
from src.analyzer import analyze_all_news
from src.mailer import build_newsletter_html, send_email

def check_env_file():
    """Ensure .env file exists. If not, copy from template."""
    env_path = os.path.join(BASE_DIR, '.env')
    env_example_path = os.path.join(BASE_DIR, '.env.example')
    
    if not os.path.exists(env_path):
        logger.warning(".env file not found!")
        if os.path.exists(env_example_path):
            logger.info(f"Copying template from .env.example to .env")
            shutil.copy(env_example_path, env_path)
            print("\n" + "="*70)
            print("IMPORTANT: A template '.env' file has been created for you in the project directory.")
            print(f"Path: {env_path}")
            print("Please open this file and configure your GEMINI_API_KEY and SMTP credentials.")
            print("="*70 + "\n")
        else:
            logger.error(".env.example template not found. Cannot auto-create .env.")
        return False
    return True

def run_test_email():
    """Send a simple test email to verify SMTP settings."""
    if not validate_config(is_dry_run=False):
        print("Configuration validation failed. Please check your .env file settings.")
        sys.exit(1)
        
    subject = "UPSC CSE Daily Brief - SMTP Connection Test"
    test_html = """
    <div style="font-family: sans-serif; padding: 20px; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; background-color: #fcfcfc;">
        <h2 style="color: #2e0854; border-bottom: 2px solid #fbbf24; padding-bottom: 8px;">SMTP Test Successful!</h2>
        <p>Hello! This is a test email sent from your <strong>UPSC Current Affairs Agent</strong>.</p>
        <p>Your SMTP configurations are correct, and email delivery is working perfectly.</p>
        <hr style="border: 0; border-top: 1px solid #eeeeee; margin: 20px 0;">
        <p style="font-size: 12px; color: #666666;">Generated on: """ + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
    </div>
    """
    
    success = send_email(subject, test_html)
    if success:
        print("Success! Test email sent successfully.")
    else:
        print("Error: Failed to send test email. Check the agent.log file for error details.")

def run_daily_agent(is_dry_run=False, force_refresh=False):
    """Run the complete agent workflow: fetch, curate, analyze, format, and mail/save."""
    if not validate_config(is_dry_run=is_dry_run):
        print("Configuration validation failed. Please check your .env file settings.")
        sys.exit(1)
        
    logger.info("Starting UPSC Current Affairs Agent run...")
    
    # Setup cache file
    date_str_file = datetime.datetime.now().strftime("%Y-%m-%d")
    cache_file = os.path.join(DATA_DIR, f"brief_{date_str_file}.json")
    
    cached_cards = []
    
    if os.path.exists(cache_file) and not force_refresh:
        logger.info(f"Loading cached UPSC study cards from {cache_file} for today...")
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_cards = json.load(f)
            logger.info(f"Successfully loaded {len(cached_cards)} study cards from cache.")
        except Exception as e:
            logger.error(f"Error reading cache file: {e}. Will regenerate.")
            cached_cards = []
            
    # Always fetch latest news and verification data to check for updates/additions
    logger.info("Fetching recent news articles...")
    articles = fetch_all_recent_news(max_hours=24)
    
    logger.info("Fetching verification and curation sources...")
    verification_data = fetch_verification_data()
    
    if not articles and not verification_data.get('insights_topics') and not cached_cards:
        logger.warning("No recent content retrieved and no cached brief found.")
        print("No content fetched. Check network connection or feed URLs.")
        return
        
    cards = []
    
    if cached_cards and not force_refresh:
        # Appending mode: find newly published articles/topics not already in cache
        logger.info("Comparing fetched articles against cached brief to identify updates...")
        seen_titles = {"".join(c for c in card['title'].lower() if c.isalnum()) for card in cached_cards}
        
        new_articles = [art for art in articles if "".join(c for c in art['title'].lower() if c.isalnum()) not in seen_titles]
        new_insights = [t for t in verification_data.get('insights_topics', []) if "".join(c for c in t['title'].lower() if c.isalnum()) not in seen_titles]
        new_youtube = [t for t in verification_data.get('youtube_topics', []) if "".join(c for c in t.lower() if c.isalnum()) not in seen_titles]
        
        new_verification_data = {
            'insights_topics': new_insights,
            'youtube_topics': new_youtube
        }
        
        logger.info(f"Identified {len(new_articles)} new raw articles, {len(new_insights)} new Insights topics, and {len(new_youtube)} new YouTube topics.")
        
        if new_articles or new_insights or new_youtube:
            logger.info("Processing and analyzing new updates via Gemini...")
            new_cards = analyze_all_news(new_articles, new_verification_data)
            
            if new_cards:
                logger.info(f"Appending {len(new_cards)} new study cards to the daily brief cache...")
                cached_cards.extend(new_cards)
                try:
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(cached_cards, f, indent=2, ensure_ascii=False)
                    logger.info(f"Updated cache saved successfully: {cache_file}")
                except Exception as e:
                    logger.error(f"Error saving updated cache: {e}")
            else:
                logger.info("No new study cards generated from updates.")
        else:
            logger.info("No newly published articles or topics found. Using cached brief as-is.")
            
        cards = cached_cards
    else:
        # Full generation mode (cache doesn't exist or --force is set)
        logger.info("Processing and analyzing all articles via Gemini...")
        cards = analyze_all_news(articles, verification_data)
        logger.info(f"Analysis complete. Generated {len(cards)} study cards.")
        
        if cards:
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cards, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved {len(cards)} generated study cards to cache: {cache_file}")
            except Exception as e:
                logger.error(f"Error saving to cache file: {e}")
                
    # 3. Format
    logger.info("Step 3: Compiling HTML newsletter...")
    html_content = build_newsletter_html(cards)
    
    # 4. Dispatch/Save
    if is_dry_run:
        output_file = os.path.join(DATA_DIR, 'test_output.html')
        logger.info(f"Dry-run enabled. Saving HTML newsletter to: {output_file}")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print("\n" + "="*70)
        print("DRY-RUN SUCCESSFUL!")
        print(f"The generated UPSC Daily Brief newsletter has been saved locally to:")
        print(f" -> {output_file}")
        print("You can double-click this file to open and preview it in a browser.")
        print("="*70 + "\n")
    else:
        date_str = datetime.datetime.now().strftime("%d %b %Y")
        subject = f"UPSC Daily Brief - {date_str}"
        logger.info("Step 4: Sending email newsletter...")
        success = send_email(subject, html_content)
        if success:
            logger.info("Daily agent workflow completed successfully.")
        else:
            logger.error("Daily agent workflow completed, but email dispatch failed.")

def main():
    parser = argparse.ArgumentParser(description="UPSC Daily Current Affairs AI Agent")
    parser.add_argument('--dry-run', action='store_true', help="Run fetch & analysis, then save to a local HTML file without emailing.")
    parser.add_argument('--test-email', action='store_true', help="Send a simple test email to verify SMTP connection.")
    parser.add_argument('--force', action='store_true', help="Force refresh and bypass cache for today's brief.")
    args = parser.parse_args()
    
    # Check that .env file exists
    env_exists = check_env_file()
    if not env_exists and not args.dry_run:
        print("Please configure the '.env' file with your credentials before running the agent.")
        sys.exit(1)
        
    if args.test_email:
        run_test_email()
    else:
        run_daily_agent(is_dry_run=args.dry_run, force_refresh=args.force)

if __name__ == '__main__':
    main()
