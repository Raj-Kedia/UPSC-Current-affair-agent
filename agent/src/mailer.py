import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import datetime
import time
from src.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, RECEIVER_EMAIL, logger

def get_recipient_display(receiver_email_str):
    """Return a clean display string for recipient(s)."""
    recipients = [e.strip() for e in receiver_email_str.split(',') if e.strip()]
    if len(recipients) == 1:
        return recipients[0]
    elif len(recipients) <= 3:
        return ", ".join(recipients)
    else:
        return f"{recipients[0]} and {len(recipients)-1} others"

def get_paper_badge_style(syllabus_topic):
    """Return styling based on GS Paper."""
    syllabus_lower = syllabus_topic.lower()
    if 'gs paper i ' in syllabus_lower or 'gs-i' in syllabus_lower:
        return 'background-color: #e3f2fd; color: #0d47a1; border: 1px solid #bbdefb;'  # Soft Blue
    elif 'gs paper ii' in syllabus_lower or 'gs-ii' in syllabus_lower:
        return 'background-color: #f3e5f5; color: #4a148c; border: 1px solid #e1bee7;'  # Soft Purple
    elif 'gs paper iii' in syllabus_lower or 'gs-iii' in syllabus_lower:
        return 'background-color: #e8f5e9; color: #1b5e20; border: 1px solid #c8e6c9;'  # Soft Green
    elif 'gs paper iv' in syllabus_lower or 'gs-iv' in syllabus_lower:
        return 'background-color: #fff3e0; color: #e65100; border: 1px solid #ffe0b2;'  # Soft Orange
    else:
        return 'background-color: #f5f5f5; color: #333333; border: 1px solid #e0e0e0;'  # Neutral Gray

def format_card_to_html(card):
    """Format a single UPSC analysis card to HTML."""
    badge_style = get_paper_badge_style(card.get('syllabus_topic', ''))
    
    # Format Prelims pointers
    prelims_html = ""
    for ptr in card.get('prelims_pointers', []):
        prelims_html += f"<li style='margin-bottom: 8px; font-size: 14px;'>📌 {ptr}</li>"
    if not prelims_html:
        prelims_html = "<li>No specific Prelims facts noted.</li>"
        
    # Format Mains concepts
    mains = card.get('mains_concepts', {})
    
    sig_html = "".join(f"<li style='margin-bottom: 6px;'>➕ {s}</li>" for s in mains.get('significance', []))
    if not sig_html:
        sig_html = "<li>No significant advantages listed.</li>"
        
    chal_html = "".join(f"<li style='margin-bottom: 6px;'>⚠️ {c}</li>" for c in mains.get('challenges', []))
    if not chal_html:
        chal_html = "<li>No significant challenges listed.</li>"
        
    # Format PYQ connection
    pyq_conn = card.get('pyq_connection', 'No direct connection found.')
    
    html = f"""
    <div style="background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); margin-bottom: 30px; border: 1px solid #eef2f5; overflow: hidden; font-family: 'Inter', Helvetica, Arial, sans-serif;">
        <!-- Card Header -->
        <div style="padding: 20px 24px; border-bottom: 1px solid #f1f4f6; background: linear-gradient(135deg, #fbfcfd 0%, #f5f7fa 100%);">
            <span style="display: inline-block; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 10px; {badge_style}">
                {card.get('syllabus_topic', 'GS Paper: General')}
            </span>
            <h2 style="margin: 0; color: #1e293b; font-size: 20px; font-weight: 700; line-height: 1.4;">
                {card.get('title', 'UPSC Current Affair')}
            </h2>
            <div style="font-size: 12px; color: #64748b; margin-top: 6px;">
                Source: <span style="font-weight: 600;">{card.get('source', 'Unknown')}</span> | Date: {card.get('date', 'N/A')}
            </div>
        </div>
        
        <!-- Card Body -->
        <div style="padding: 24px;">
            <!-- Context -->
            <div style="margin-bottom: 20px;">
                <h3 style="color: #475569; font-size: 14px; font-weight: 600; margin: 0 0 8px 0; text-transform: uppercase; letter-spacing: 0.5px;">Context / Why in News?</h3>
                <p style="color: #334155; font-size: 14px; line-height: 1.6; margin: 0; background-color: #f8fafc; padding: 12px 16px; border-left: 4px solid #64748b; border-radius: 4px;">
                    {card.get('context', '')}
                </p>
            </div>
            
            <!-- Prelims Pointers -->
            <div style="margin-bottom: 20px; background-color: #fffdf5; border: 1px solid #fef3c7; border-radius: 8px; padding: 16px;">
                <h3 style="color: #b45309; font-size: 14px; font-weight: 600; margin: 0 0 10px 0; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #fde68a; padding-bottom: 4px;">🎯 Prelims Pointers (Key Facts)</h3>
                <ul style="margin: 0; padding-left: 0; list-style-type: none; color: #451a03; line-height: 1.5;">
                    {prelims_html}
                </ul>
            </div>
            
            <!-- Mains Concepts -->
            <div style="margin-bottom: 20px;">
                <h3 style="color: #0f172a; font-size: 14px; font-weight: 600; margin: 0 0 12px 0; text-transform: uppercase; letter-spacing: 0.5px;">💡 Mains Dimension</h3>
                
                <!-- Background -->
                {f'''
                <div style="margin-bottom: 12px;">
                    <div style="font-size: 13px; font-weight: 600; color: #64748b; margin-bottom: 4px;">Background / Core Issue:</div>
                    <div style="font-size: 14px; color: #334155; line-height: 1.6; padding-left: 10px; border-left: 2px solid #cbd5e1;">{mains.get('background', '')}</div>
                </div>
                ''' if mains.get('background') else ''}
                
                <!-- Significance -->
                <div style="margin-bottom: 12px;">
                    <div style="font-size: 13px; font-weight: 600; color: #166534; margin-bottom: 4px;">Significance / Key Arguments:</div>
                    <ul style="margin: 0; padding-left: 20px; color: #334155; font-size: 14px; line-height: 1.6;">
                        {sig_html}
                    </ul>
                </div>
                
                <!-- Challenges -->
                <div style="margin-bottom: 12px;">
                    <div style="font-size: 13px; font-weight: 600; color: #991b1b; margin-bottom: 4px;">Challenges / Critical Concerns:</div>
                    <ul style="margin: 0; padding-left: 20px; color: #334155; font-size: 14px; line-height: 1.6;">
                        {chal_html}
                    </ul>
                </div>
                
                <!-- Way Forward -->
                {f'''
                <div style="margin-top: 12px; background-color: #f0fdf4; border: 1px solid #dcfce7; border-radius: 6px; padding: 12px 14px;">
                    <div style="font-size: 13px; font-weight: 600; color: #166534; margin-bottom: 4px;">Way Forward:</div>
                    <div style="font-size: 14px; color: #14532d; line-height: 1.5;">{mains.get('way_forward', '')}</div>
                </div>
                ''' if mains.get('way_forward') else ''}
            </div>
            
            <!-- PYQ Connection -->
            <div style="background-color: #eff6ff; border: 1px solid #dbeafe; border-radius: 8px; padding: 16px; margin-bottom: 15px;">
                <h3 style="color: #1d4ed8; font-size: 14px; font-weight: 600; margin: 0 0 8px 0; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #bfdbfe; padding-bottom: 4px;">📚 Connection to UPSC PYQs</h3>
                <p style="color: #1e3a8a; font-size: 13.5px; line-height: 1.5; margin: 0;">
                    {pyq_conn}
                </p>
            </div>
        </div>
        
        <!-- Card Footer -->
        <div style="background-color: #f8fafc; border-top: 1px solid #eef2f5; padding: 12px 24px; text-align: right;">
            <a href="{card.get('link', '#')}" target="_blank" style="color: #2563eb; text-decoration: none; font-size: 13px; font-weight: 600; display: inline-block;">
                Read Full Article &rarr;
            </a>
        </div>
    </div>
    """
    return html

def build_newsletter_html(cards, week_label=None):
    """Compile all cards into a single beautiful HTML email newsletter for the weekly edition."""
    cards_html = ""
    for card in cards:
        cards_html += format_card_to_html(card)
        
    if not cards:
        cards_html = """
        <div style="text-align: center; padding: 40px; color: #64748b; font-family: sans-serif;">
            <p style="font-size: 16px; margin-bottom: 8px;">No major UPSC-relevant news updates occurred during this weekly review cycle.</p>
            <p style="font-size: 14px;">Next weekly digest will compile upcoming issues!</p>
        </div>
        """
        
    if not week_label:
        today = datetime.datetime.now()
        start_of_week = today - datetime.timedelta(days=7)
        week_label = f"{start_of_week.strftime('%b %d')} – {today.strftime('%b %d, %Y')}"
    
    # List of motivational quotes for UPSC aspirants
    quotes = [
        "Success is not final, failure is not fatal: it is the courage to continue that counts. – Winston Churchill",
        "The secret of getting ahead is getting started. – Mark Twain",
        "Our greatest weakness lies in giving up. The most certain way to succeed is always to try just one more time. – Thomas A. Edison",
        "It always seems impossible until it's done. – Nelson Mandela",
        "Go confidently in the direction of your dreams. Live the life you have imagined. – Henry David Thoreau"
    ]
    import random
    quote = random.choice(quotes)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>UPSC CSE Weekly Digest</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    </head>
    <body style="margin: 0; padding: 0; background-color: #f3f4f6; -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%;">
        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f3f4f6; table-layout: fixed;">
            <tr>
                <td align="center" style="padding: 30px 10px;">
                    <!-- Email Wrapper -->
                    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 680px; width: 100%;">
                        
                        <!-- Header -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #1e1b4b 0%, #311042 100%); border-radius: 12px 12px 0 0; padding: 35px 30px; text-align: center; border-bottom: 4px solid #fbbf24;">
                                <h1 style="margin: 0; color: #ffffff; font-family: 'Inter', sans-serif; font-size: 28px; font-weight: 700; letter-spacing: 0.5px;">UPSC CSE Weekly Digest</h1>
                                <p style="margin: 8px 0 0 0; color: #cbd5e1; font-family: 'Inter', sans-serif; font-size: 14px; font-weight: 500; text-transform: uppercase; letter-spacing: 2px;">
                                    Weekly Current Affairs Analysis & Mains PYQ Synthesis
                                </p>
                                <div style="display: inline-block; background-color: rgba(251, 191, 36, 0.15); color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.3); font-family: 'Inter', sans-serif; font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 15px; margin-top: 15px;">
                                    📅 Week of {week_label}
                                </div>
                            </td>
                        </tr>
                        
                        <!-- Main Content -->
                        <tr>
                            <td style="padding: 30px 0;">
                                {cards_html}
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="background-color: #1e293b; border-radius: 0 0 12px 12px; padding: 30px 24px; text-align: center; color: #94a3b8; font-family: 'Inter', sans-serif;">
                                <p style="margin: 0 0 15px 0; font-size: 13.5px; font-style: italic; line-height: 1.5; color: #e2e8f0; max-width: 500px; display: inline-block;">
                                    "{quote}"
                                </p>
                                <div style="border-top: 1px solid #334155; padding-top: 15px; margin-top: 15px; font-size: 11px; line-height: 1.5;">
                                    This weekly newsletter is synthesized and dispatched by your UPSC AI Intelligence Agent.<br>
                                    Sent to registered active subscribers.<br>
                                    To manage your weekly delivery preferences, log into your UPSC Agent dashboard.
                                </div>
                            </td>
                        </tr>
                        
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return html

def send_email(subject, html_content, recipients=None, max_retries=3, retry_delay=15):
    """Send an HTML email to target recipients, falling back to active DB subscribers or RECEIVER_EMAIL."""
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.error("SMTP credentials are not configured. Cannot send email.")
        return False
        
    target_recipients = []
    if recipients:
        if isinstance(recipients, str):
            target_recipients = [e.strip() for e in recipients.split(',') if e.strip()]
        elif isinstance(recipients, list):
            target_recipients = [e.strip() for e in recipients if e.strip()]
            
    if not target_recipients:
        # Check active database subscribers
        try:
            from src.db import get_active_subscriber_emails
            active_emails = get_active_subscriber_emails()
            if active_emails:
                target_recipients = active_emails
        except Exception as e:
            logger.warning(f"Could not fetch active subscribers from DB: {e}")
            
    if not target_recipients and RECEIVER_EMAIL:
        target_recipients = [e.strip() for e in RECEIVER_EMAIL.split(',') if e.strip()]
        
    if not target_recipients:
        logger.error("No valid receiver email addresses found (neither provided, in DB, nor in RECEIVER_EMAIL).")
        return False
        
    # Deduplicate recipients
    target_recipients = list(dict.fromkeys(target_recipients))
    
    for attempt in range(max_retries):
        if attempt > 0:
            logger.info(f"Retrying email dispatch in {retry_delay} seconds (attempt {attempt + 1}/{max_retries})...")
            time.sleep(retry_delay)
            
        logger.info(f"Preparing to send weekly digest to {len(target_recipients)} recipient(s): {', '.join(target_recipients)} via {SMTP_HOST}:{SMTP_PORT} (attempt {attempt + 1}/{max_retries})...")
        
        try:
            # Connect to SMTP server
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
            server.ehlo()
            server.starttls() # Secure connection
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            
            # Send to each recipient individually so recipients don't expose each other's emails
            sent_count = 0
            for recipient in target_recipients:
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = SMTP_USER
                msg['To'] = recipient
                msg.attach(MIMEText(html_content, 'html'))
                server.sendmail(SMTP_USER, [recipient], msg.as_string())
                sent_count += 1
                
            server.quit()
            logger.info(f"Weekly newsletter sent successfully to {sent_count} subscriber(s)!")
            return True
        except Exception as e:
            logger.error(f"Failed to send email on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                return False
