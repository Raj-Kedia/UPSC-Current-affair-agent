import feedparser
from bs4 import BeautifulSoup
import datetime
import time
import requests
import urllib3
from src.config import logger

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

FEEDS = {
    'PIB': 'https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1',
    'The Hindu National': 'https://www.thehindu.com/news/national/feeder/default.rss',
    'The Hindu Opinion': 'https://www.thehindu.com/opinion/feeder/default.rss',
    'The Hindu Business': 'https://www.thehindu.com/business/feeder/default.rss',
    'The Hindu Sci-Tech': 'https://www.thehindu.com/sci-tech/feeder/default.rss'
}

def clean_html(html_text):
    """Strip HTML tags and clean up whitespace."""
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, "html.parser")
    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.extract()
    text = soup.get_text()
    # Break into lines and remove leading and trailing space on each
    lines = (line.strip() for line in text.splitlines())
    # Break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    # Drop blank lines
    return '\n'.join(chunk for chunk in chunks if chunk)

def fetch_feed_articles(feed_name, url, max_hours=24):
    """Fetch articles from a single RSS feed published within the last max_hours."""
    logger.info(f"Fetching feed '{feed_name}' from: {url}")
    articles = []
    
    try:
        # Parse feed
        feed = feedparser.parse(url)
        
        now = datetime.datetime.utcnow()
        time_threshold = now - datetime.timedelta(hours=max_hours)
        
        for entry in feed.entries:
            title = entry.get('title', '').strip()
            link = entry.get('link', '').strip()
            summary = entry.get('summary', '').strip()
            description = entry.get('description', '').strip()
            
            # Use description if summary is empty
            content = summary if len(summary) > len(description) else description
            content_cleaned = clean_html(content)
            
            # Get published date
            published_parsed = entry.get('published_parsed')
            published_dt = None
            
            if published_parsed:
                try:
                    published_dt = datetime.datetime(*published_parsed[:6])
                except Exception:
                    pass
            
            # Fallback parsing for published string
            if not published_dt and entry.get('published'):
                for fmt in ('%a, %d %b %Y %H:%M:%S %Z', '%a, %d %b %Y %H:%M:%S %z', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%SZ'):
                    try:
                        published_dt = datetime.datetime.strptime(entry.published, fmt)
                        # Remove timezone info for comparison
                        if published_dt.tzinfo:
                            published_dt = published_dt.replace(tzinfo=None)
                        break
                    except ValueError:
                        continue
            
            # If we still can't parse the date, we check the list of articles and assume it's current if it lacks a timestamp
            is_recent = True
            if published_dt:
                is_recent = published_dt >= time_threshold
            
            if is_recent:
                articles.append({
                    'source': feed_name,
                    'title': title,
                    'link': link,
                    'summary': content_cleaned,
                    'published': published_dt.strftime('%Y-%m-%d %H:%M:%S') if published_dt else 'N/A'
                })
                
        logger.info(f"Retrieved {len(articles)} recent articles from '{feed_name}'")
    except Exception as e:
        logger.error(f"Error fetching feed '{feed_name}': {e}")
        
    return articles

def fetch_all_recent_news(max_hours=24):
    """Fetch recent news from all registered feeds, deduplicate them, and return."""
    all_articles = []
    seen_titles = set()
    
    for feed_name, url in FEEDS.items():
        feed_articles = fetch_feed_articles(feed_name, url, max_hours)
        for art in feed_articles:
            # Simple deduplication based on normalized title
            norm_title = "".join(c for c in art['title'].lower() if c.isalnum())
            if norm_title not in seen_titles:
                seen_titles.add(norm_title)
                all_articles.append(art)
                
    logger.info(f"Total deduplicated news articles fetched: {len(all_articles)}")
    return all_articles

def fetch_youtube_topics(channel_name, channel_id, max_hours=30):
    """Fetch video titles from a YouTube channel feed published within max_hours."""
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    logger.info(f"Fetching YouTube feed '{channel_name}' from: {url}")
    topics = []
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        r = requests.get(url, headers=headers, timeout=15, verify=False)
        if r.status_code != 200:
            logger.error(f"Failed to fetch YouTube feed for {channel_name}: Status {r.status_code}")
            return []
            
        feed = feedparser.parse(r.content)
        now = datetime.datetime.utcnow()
        time_threshold = now - datetime.timedelta(hours=max_hours)
        
        for entry in feed.entries:
            published_str = entry.get('published') or entry.get('updated')
            published_dt = None
            if published_str:
                try:
                    clean_str = published_str.split('+')[0].split('Z')[0]
                    published_dt = datetime.datetime.strptime(clean_str, '%Y-%m-%dT%H:%M:%S')
                except Exception:
                    pass
            
            is_recent = True
            if published_dt:
                is_recent = published_dt >= time_threshold
                
            if is_recent:
                title = entry.get('title', '').strip()
                if title:
                    topics.append(title)
                    
        logger.info(f"Retrieved {len(topics)} recent video titles from YouTube '{channel_name}'")
    except Exception as e:
        logger.error(f"Error fetching YouTube feed for {channel_name}: {e}")
        
    return topics

def fetch_insights_ca_topics(max_hours=30):
    """Fetch daily current affairs topics and their detailed body texts from Insights on India."""
    feed_url = "https://www.insightsonindia.com/feed/"
    logger.info(f"Fetching Insights on India main feed from: {feed_url}")
    
    topics = []
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        r = requests.get(feed_url, headers=headers, timeout=15, verify=False)
        if r.status_code != 200:
            logger.error(f"Failed to fetch Insights main feed: Status {r.status_code}")
            return []
            
        feed = feedparser.parse(r.content)
        
        target_entry = None
        for entry in feed.entries:
            title = entry.get('title', '')
            title_lower = title.lower()
            if "current affairs" in title_lower and not "quiz" in title_lower and not "instadart" in title_lower:
                target_entry = entry
                break
                
        if not target_entry:
            logger.warning("No recent Insights Daily Current Affairs post found in feed.")
            return []
            
        post_url = target_entry.get('link')
        post_title = target_entry.get('title')
        logger.info(f"Found Daily CA post: '{post_title}' at URL: {post_url}")
        
        pr = requests.get(post_url, headers=headers, timeout=15, verify=False)
        if pr.status_code != 200:
            logger.error(f"Failed to fetch Insights post HTML: Status {pr.status_code}")
            return []
            
        soup = BeautifulSoup(pr.text, 'html.parser')
        content_div = soup.find('div', class_='entry-content')
        if not content_div:
            logger.warning("Could not find div.entry-content in Insights post.")
            return []
            
        # Extract topics using class-based structure
        headers_divs = content_div.find_all('div', class_='ca-topic-header')
        
        if headers_divs:
            logger.info(f"Parsing Insights topics using class-based structure (found {len(headers_divs)} topics)...")
            for header in headers_divs:
                h2 = header.find('h2')
                title_text = h2.get_text(strip=True) if h2 else ""
                if not title_text:
                    continue
                    
                body_text = ""
                curr = header.next_sibling
                while curr:
                    if curr.name == 'div' and 'article-body-column' in curr.get('class', []):
                        body_text = curr.get_text(separator="\n", strip=True)
                        break
                    if curr.name == 'div' and 'ca-topic-header' in curr.get('class', []):
                        break
                    curr = curr.next_sibling
                
                topics.append({
                    'title': title_text,
                    'source_text': body_text,
                    'url': post_url
                })
        else:
            # Fallback
            logger.info("Parsing Insights topics using fallback h2 sibling structure...")
            h2s = content_div.find_all('h2')
            for idx, h2 in enumerate(h2s):
                title_text = h2.get_text(strip=True)
                if not title_text or any(w in title_text.lower() for w in ['branches', 'about us', 'courses', 'insights ias']):
                    continue
                    
                body_parts = []
                curr = h2.next_sibling
                while curr:
                    if curr.name == 'h2':
                        break
                    if curr.name:
                        text = curr.get_text(strip=True)
                        if text:
                            body_parts.append(text)
                    curr = curr.next_sibling
                    
                body_text = "\n".join(body_parts)
                topics.append({
                    'title': title_text,
                    'source_text': body_text,
                    'url': post_url
                })
                
        logger.info(f"Successfully scraped {len(topics)} topics from Insights on India post.")
    except Exception as e:
        logger.error(f"Error scraping Insights on India: {e}")
        
    return topics

def fetch_verification_data():
    """Fetch verification topics from Insights on India and YouTube channels."""
    verification_data = {
        'insights_topics': [],
        'youtube_topics': []
    }
    
    insights_topics = fetch_insights_ca_topics(max_hours=30)
    verification_data['insights_topics'] = insights_topics
    
    studyiq_topics = fetch_youtube_topics("StudyIQ UPSC CSE", "UCl9HsnUFaRBrkql1Gly6ICQ", max_hours=30)
    verification_data['youtube_topics'].extend(studyiq_topics)
    
    onlyias_topics = fetch_youtube_topics("PW OnlyIAS", "UC4qbM7cBX0xxNbCY2D7rj4A", max_hours=30)
    verification_data['youtube_topics'].extend(onlyias_topics)
    
    total_insights = len(insights_topics)
    total_yt = len(verification_data['youtube_topics'])
    logger.info(f"Verification data summary: {total_insights} Insights topics, {total_yt} YouTube topics.")
    
    return verification_data

def search_ddg(query):
    """Search DuckDuckGo and return top snippets."""
    import urllib.parse
    logger.info(f"Searching DuckDuckGo for: {query}")
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        r = requests.get(url, headers=headers, timeout=15, verify=False)
        if r.status_code != 200:
            logger.warning(f"DuckDuckGo search failed with status: {r.status_code}")
            return []
            
        soup = BeautifulSoup(r.text, 'html.parser')
        results = []
        for a in soup.find_all('a', class_='result__snippet')[:3]:
            parent = a.find_parent('div', class_='result__body')
            if parent:
                title_elem = parent.find('a', class_='result__url')
                title = title_elem.get_text(strip=True) if title_elem else "No Title"
                link = title_elem['href'] if title_elem and 'href' in title_elem.attrs else ""
                
                # Clean DDG redirect links
                if link.startswith('//duckduckgo.com/l/?uddg='):
                    parts = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                    if 'uddg' in parts:
                        link = parts['uddg'][0]
                elif link.startswith('//'):
                    link = 'https:' + link
                    
                snippet = a.get_text(strip=True)
                results.append({
                    'title': title,
                    'link': link,
                    'snippet': snippet
                })
        return results
    except Exception as e:
        logger.error(f"Error searching DuckDuckGo for '{query}': {e}")
        return []
