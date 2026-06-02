import json
import os
import re
import time
import datetime
import google.generativeai as genai
from src.config import GEMINI_API_KEY, GEMINI_MODEL, DATA_DIR, logger

# Initialize Gemini API
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY environment variable is not set. API calls will fail.")

def generate_content_with_retry(model, prompt, max_retries=5, initial_delay=2):
    """Call generate_content with exponential backoff on rate limit/resource exhaustion errors."""
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                logger.info(f"Retrying API call in {delay} seconds (attempt {attempt + 1}/{max_retries})...")
                time.sleep(delay)
            return model.generate_content(prompt)
        except Exception as e:
            err_msg = str(e)
            is_rate_limit = "429" in err_msg or "ResourceExhausted" in err_msg or "quota" in err_msg.lower()
            # Daily limits will not reset in a short time, so don't block by retrying
            is_daily_limit = "requestsperday" in err_msg.lower().replace("_", "").replace("-", "") or "daily" in err_msg.lower()
            
            if is_rate_limit and not is_daily_limit and attempt < max_retries - 1:
                logger.warning(f"Rate limit hit: {e}. Retrying...")
                delay = max(25, delay * 2)
            else:
                raise e

def load_local_pyqs():
    """Load local mains PYQs database if it exists."""
    path = os.path.join(DATA_DIR, 'upsc_mains_pyqs.json')
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading local PYQs: {e}")
    return {}

def extract_keywords(text):
    """Extract clean search keywords from text."""
    # Simple stop words list
    stop_words = {
        'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are', 'arent', 'as', 
        'at', 'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but', 'by', 'cant', 'cannot', 
        'could', 'couldnt', 'did', 'didnt', 'do', 'does', 'doesnt', 'doing', 'dont', 'down', 'during', 'each', 
        'few', 'for', 'from', 'further', 'had', 'hadnt', 'has', 'hasnt', 'have', 'havent', 'having', 'he', 'hed', 
        'hell', 'hes', 'her', 'here', 'heres', 'hers', 'herself', 'him', 'himself', 'his', 'how', 'hows', 'i', 
        'id', 'ill', 'im', 'ive', 'if', 'in', 'into', 'is', 'isnt', 'it', 'its', 'itself', 'lets', 'me', 'more', 
        'most', 'mustnt', 'my', 'myself', 'no', 'nor', 'not', 'of', 'off', 'on', 'once', 'only', 'or', 'other', 
        'ought', 'our', 'ours', 'ourselves', 'out', 'over', 'own', 'same', 'shant', 'she', 'shed', 'shell', 'shes', 
        'should', 'shouldnt', 'so', 'some', 'such', 'than', 'that', 'thats', 'the', 'their', 'theirs', 'them', 
        'themselves', 'then', 'there', 'theres', 'these', 'they', 'theyd', 'theyll', 'theyre', 'theyve', 'this', 
        'those', 'through', 'to', 'too', 'under', 'until', 'up', 'very', 'was', 'wasnt', 'we', 'wed', 'well', 
        'were', 'weve', 'werent', 'what', 'whats', 'when', 'whens', 'where', 'wheres', 'which', 'while', 'who', 
        'whos', 'whom', 'why', 'whys', 'with', 'wont', 'would', 'wouldnt', 'you', 'youd', 'youll', 'youre', 'youve', 
        'your', 'yours', 'yourself', 'yourselves', 'news', 'india', 'indian', 'government', 'national', 'state', 'policy'
    }
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    return [w for w in words if w not in stop_words]

def search_related_mains_pyqs(title, summary, local_pyqs, max_results=3):
    """Search local mains PYQs database for related questions based on keywords."""
    if not local_pyqs:
        return []
    
    keywords = extract_keywords(title + " " + summary)
    if not keywords:
        return []
    
    matches = []
    # Search in GSI, GSII, GSIII lists
    for paper_key, questions in local_pyqs.items():
        for q in questions:
            score = 0
            q_text = q.get('Question', '').lower()
            for kw in keywords:
                if kw in q_text:
                    score += 1
            if score > 0:
                matches.append((score, q, paper_key))
                
    # Sort by score descending
    matches.sort(key=lambda x: x[0], reverse=True)
    
    unique_matches = []
    seen_qs = set()
    for _, q, paper in matches:
        q_text = q.get('Question')
        if q_text not in seen_qs:
            seen_qs.add(q_text)
            unique_matches.append({
                'Paper': paper,
                'Year': q.get('Year'),
                'Question': q_text,
                'Marks': q.get('Marks')
            })
            if len(unique_matches) >= max_results:
                break
                
    return unique_matches

# UPSC GS Taxonomy — modeled after how top UPSC YouTube educators (StudyIQ, OnlyIAS, Drishti IAS) segregate daily news
UPSC_TAXONOMY = """
GS Paper I  → Art & Culture | Ancient/Medieval/Modern History | Indian Geography | World Geography | Social Issues (women, poverty, urbanisation)
GS Paper II → Indian Polity & Constitution | Governance & Public Policy | Social Justice (health, education, welfare schemes) | International Relations & Diplomacy | Bilateral/Multilateral Bodies
GS Paper III → Indian Economy & Development | Agriculture & Food Security | Infrastructure (transport, energy, urban) | Science & Technology | Environment & Ecology | Biodiversity & Conservation | Disaster Management | Internal Security

EXCLUDE: Local crime, road accidents, party politics/mudslinging, celebrity gossip, product launches, routine sports (unless international achievement/policy angle).
INDEX SCORING: 0 = Not relevant | 5 = Marginally relevant | 7 = Relevant | 10 = Highly exam-focused (policy, treaty, SC ruling, major report, constitutional matter)
"""

def filter_upsc_relevant_news(articles):
    """Stage 1: Use Gemini to filter and select only UPSC relevant articles using taxonomy scoring."""
    if not articles:
        return []
        
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is not set. Running in MOCK MODE and selecting first 5 articles.")
        return articles[:5]
        
    logger.info(f"Filtering {len(articles)} articles for UPSC relevance using taxonomy scoring...")
    
    # Format list for the prompt
    articles_list_str = ""
    for idx, art in enumerate(articles):
        articles_list_str += f"[{idx}] Title: {art['title']}\nSummary: {art['summary'][:200]}...\n\n"
        
    prompt = f"""You are a senior UPSC CSE mentor. Segregate and score each news article for UPSC exam relevance.

UPSC TAXONOMY AND SCORING GUIDE:
{UPSC_TAXONOMY}

For each article:
1. Identify the GS Paper (I / II / III) and specific sub-topic from the taxonomy.
2. Assign a relevance score (0–10). Score 7+ means select it.
3. Only select articles with score >= 7.

Return ONLY a raw JSON object with two keys — no markdown, no explanation:
- "scored": list of objects with keys: "index" (int), "paper" (string like "GS Paper II"), "topic" (string), "score" (int)
- "selected_indices": list of ints (only those with score >= 7)

News Articles:
{articles_list_str}

Output format example:
{{"scored": [{{"index": 0, "paper": "GS Paper II", "topic": "Indian Polity & Constitution", "score": 8}}, ...], "selected_indices": [0, 3, 5]}}"""

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = generate_content_with_retry(model, prompt)
        text = response.text.strip()
        
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        
        result = json.loads(text.strip(), strict=False)
        selected_indices = result.get('selected_indices', [])
        scored = {item['index']: item for item in result.get('scored', [])}
        
        filtered_articles = []
        for i in selected_indices:
            if 0 <= i < len(articles):
                art = articles[i].copy()
                # Attach pre-classified syllabus topic to save one API call later
                if i in scored:
                    art['_pre_classified'] = f"{scored[i]['paper']}: {scored[i]['topic']}"
                filtered_articles.append(art)
                
        logger.info(f"Taxonomy scoring selected {len(filtered_articles)} / {len(articles)} relevant articles.")
        return filtered_articles
    except Exception as e:
        logger.error(f"Error in UPSC taxonomy filtering stage: {e}")
        # Fallback: return first 5 articles
        return articles[:5]

def analyze_article(article, local_pyqs):
    """Stage 2: Perform deep UPSC study card analysis on a single article."""
    if not GEMINI_API_KEY:
        # Generate a high-quality mock study card based on keywords
        title_lower = article['title'].lower()
        summary_lower = article['summary'].lower()
        text_lower = title_lower + " " + summary_lower
        
        paper = "GS Paper III"
        subtopic = "Economic Development"
        if any(w in text_lower for w in ["court", "constitution", "polity", "bill", "act", "judiciary", "election", "parliament"]):
            paper = "GS Paper II"
            subtopic = "Polity and Governance"
        elif any(w in text_lower for w in ["treaty", "china", "usa", "summit", "unsc", "bilateral", "russia", "global", "visit"]):
            paper = "GS Paper II"
            subtopic = "International Relations"
        elif any(w in text_lower for w in ["history", "chola", "temple", "excavation", "monument", "culture", "earthquake", "monsoon"]):
            paper = "GS Paper I"
            subtopic = "Art & Culture / Geography"
        elif any(w in text_lower for w in ["pollution", "carbon", "biodiversity", "species", "forest", "wildlife", "tiger", "climate", "conservation"]):
            paper = "GS Paper III"
            subtopic = "Environment and Ecology"
            
        matching_pyqs = search_related_mains_pyqs(article['title'], article['summary'], local_pyqs)
        pyq_ref = "None found in local database. In UPSC Prelims, questions on similar lines are frequently asked."
        if matching_pyqs:
            pyq_ref = f"This relates to Mains question from {matching_pyqs[0]['Year']} ({matching_pyqs[0]['Paper']}): '{matching_pyqs[0]['Question']}'"
            
        return {
            'title': article['title'],
            'syllabus_topic': f"{paper}: {subtopic}",
            'context': f"This is in the news because of developments concerning this topic. [MOCK ANALYSIS: Add GEMINI_API_KEY to .env for real AI analysis]",
            'prelims_pointers': [
                f"Fact 1: Key entity mentioned is related to {article['source']}.",
                "Fact 2: Nodal agency or regulatory oversight is typically under relevant Central Ministries.",
                "Fact 3: Understanding static details of this concept is crucial for UPSC Prelims."
            ],
            'mains_concepts': {
                'background': f"The historical perspective and origin of this issue, as summarized: {article['summary'][:200]}...",
                'significance': [
                    "Promotes institutional efficiency and better resource allocation.",
                    "Enhances transparency and builds public trust.",
                    "Aligns national policies with global best practices."
                ],
                'challenges': [
                    "Potential hurdles in standard implementation and administrative capacity.",
                    "Financial constraints and high cost of compliance/transition.",
                    "Need for consensus among various state and central stakeholders."
                ],
                'way_forward': "A multi-stakeholder approach combining legislative updates, capacity building, and robust oversight is essential to realize the full benefits."
            },
            'pyq_connection': f"Connects to UPSC syllabus theme. {pyq_ref}",
            'link': article['link'],
            'source': article['source'],
            'date': article.get('published', 'N/A')
        }

    logger.info(f"Analyzing article: {article['title']}")
    
    # Find matching PYQs
    matching_pyqs = search_related_mains_pyqs(article['title'], article['summary'], local_pyqs)
    
    pyqs_str = "None found in local database."
    if matching_pyqs:
        pyqs_str = ""
        for i, q in enumerate(matching_pyqs):
            pyqs_str += f"{i+1}. [{q['Paper']} - {q['Year']} - {q['Marks']} Marks]: {q['Question']}\n"
            
    prompt = f"""You are a senior UPSC CSE analyst and subject matter expert.
Create a comprehensive, high-yield current affairs study card for the following news article.

Article Title: {article['title']}
Article Summary: {article['summary']}
Article Link: {article['link']}
Article Source: {article['source']}

Here are related past year mains questions from our database for context:
{pyqs_str}

Your analysis must be detailed, accurate, and tailored specifically to UPSC CSE standards. 
You must output a single, valid JSON object containing the following keys (no markdown code blocks, just raw JSON):

- "title": A short, clear headline for the current affairs card.
- "syllabus_topic": The General Studies paper (GS I, II, III, or IV) and specific syllabus keyword(s) matching this news.
- "context": A concise explanation of why this topic is in the news.
- "prelims_pointers": A JSON array of strings containing high-yield, specific facts to remember for the Prelims exam (schemes, nodal ministries, constitutional articles, definitions, reports, locations, international bodies, species, etc.).
- "mains_concepts": A JSON object containing:
    - "background": The historical/conceptual background of the issue.
    - "significance": Why this is important / arguments in favor / benefits (bullet points).
    - "challenges": Key challenges / concerns / criticisms (bullet points).
    - "way_forward": Constructive suggestions / recommendations / concluding thoughts.
- "pyq_connection": A detailed explanation of how this connects to past UPSC papers (both Prelims and Mains). Connect to the provided mains questions if relevant, or fetch other past year questions (e.g., "In Prelims 2021, UPSC asked about... this news on sovereign gold bonds relates directly to that concept...").

Format the output strictly as JSON. Ensure strings are properly escaped. Do not wrap the JSON in ```json ... ``` blocks."""

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = generate_content_with_retry(model, prompt)
        text = response.text.strip()
        
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            
        card_data = json.loads(text.strip(), strict=False)
        card_data['link'] = article['link']
        card_data['source'] = article['source']
        card_data['date'] = article['published']
        return card_data
    except Exception as e:
        logger.error(f"Error analyzing article '{article['title']}': {e}")
        # Return a fallback simplified card structure on failure
        return {
            'title': article['title'],
            'syllabus_topic': 'GS Paper I/II/III: Current Affairs',
            'context': 'Failed to generate deep AI analysis due to an error.',
            'prelims_pointers': ['Source: ' + article['source'], 'Read full article at link.'],
            'mains_concepts': {
                'background': article['summary'][:500] + '...',
                'significance': [],
                'challenges': [],
                'way_forward': 'Check original source for full details.'
            },
            'pyq_connection': 'N/A',
            'link': article['link'],
            'source': article['source'],
            'date': article['published'],
            'error': str(e)
        }

def curate_news_with_verification(articles, verification_data):
    """Filter raw articles and synthesize missing key topics from Insights on India and YouTube."""
    if not articles:
        return []
        
    if not verification_data or (not verification_data.get('insights_topics') and not verification_data.get('youtube_topics')):
        logger.info("No verification data provided. Running standard UPSC news filtering.")
        return filter_upsc_relevant_news(articles)
        
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is not set. Running in MOCK MODE.")
        # Return first 5 raw articles + first 2 insights topics as mock synthesis
        selected = articles[:5]
        for t in verification_data.get('insights_topics', [])[:2]:
            selected.append({
                'source': 'InsightsIAS Curation',
                'title': t['title'],
                'link': t['url'],
                'summary': t['source_text'],
                'published': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        return selected
        
    logger.info("Filtering and curating news articles using verification sources...")
    
    articles_list_str = ""
    for idx, art in enumerate(articles):
        articles_list_str += f"[{idx}] Title: {art['title']}\nSummary: {art['summary'][:200]}...\n\n"
        
    insights_list = verification_data.get('insights_topics', [])
    youtube_list = verification_data.get('youtube_topics', [])
    
    insights_str = "\n".join(f"- {t['title']}" for t in insights_list)
    youtube_str = "\n".join(f"- {t}" for t in youtube_list)
    
    prompt = f"""You are an expert UPSC Civil Services Examination (CSE) mentor and senior content curator.
We have a list of daily raw news articles, and we also have verified UPSC topics of the day from a top UPSC website and trending YouTube channels.

Verified UPSC Topics of the Day (Insights on India):
{insights_str if insights_str else "None"}

Trending YouTube Discussion Topics:
{youtube_str if youtube_str else "None"}

Raw News Articles:
{articles_list_str}

Task:
1. Analyze the raw news articles and select the ones that are highly relevant to the UPSC CSE syllabus (GS Paper I, II, or III). Prioritize articles that match or relate to the verified or trending topics.
2. For the verified UPSC topics of the day (Insights on India) and the trending YouTube topics, determine which of these topics are already matched/covered by the raw news articles you selected.

Output Format:
You must return a single, valid JSON object containing exactly these three keys (no markdown code blocks, just raw JSON):
- "selected_raw_indices": A list of integers representing the indices of the raw articles to select.
- "matched_insights_titles": A list of strings containing the exact titles of the "Verified UPSC Topics of the Day (Insights on India)" that are matched/covered by your selected raw articles.
- "matched_youtube_titles": A list of strings containing the exact titles of the "Trending YouTube Discussion Topics" that are matched/covered by your selected raw articles.

Example Output:
{{
    "selected_raw_indices": [0, 3, 5],
    "matched_insights_titles": ["The PM SVANidhi Completes Six Years of Empowering Street Vendors"],
    "matched_youtube_titles": ["1 June, 2026 Editorial Discussion | Three Language, Tribal Reservation, Pocso and Abortion"]
}}"""

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = generate_content_with_retry(model, prompt)
        text = response.text.strip()
        
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            
        result = json.loads(text.strip(), strict=False)
        selected_indices = result.get('selected_raw_indices', [])
        matched_insights_titles = set(result.get('matched_insights_titles', []))
        matched_youtube_titles = set(result.get('matched_youtube_titles', []))
        
        curated_articles = [articles[i] for i in selected_indices if 0 <= i < len(articles)]
        logger.info(f"Gemini selected {len(curated_articles)} / {len(articles)} raw articles.")
        
        # Identify unmatched InsightsIAS topics and synthesize them
        unmatched_insights_count = 0
        for topic in insights_list:
            is_matched = False
            topic_title_lower = topic['title'].lower()
            
            for mt in matched_insights_titles:
                if mt.lower() in topic_title_lower or topic_title_lower in mt.lower():
                    is_matched = True
                    break
                    
            if not is_matched:
                logger.info(f"Topic '{topic['title']}' is unmatched in news feeds. Synthesizing article from InsightsIAS...")
                
                summary = topic['source_text']
                if len(summary) > 2500:
                    summary = summary[:2500] + "..."
                    
                curated_articles.append({
                    'source': 'InsightsIAS Curation',
                    'title': topic['title'],
                    'link': topic['url'],
                    'summary': summary,
                    'published': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                unmatched_insights_count += 1
                
        # Identify unmatched YouTube topics and run web search if not covered by InsightsIAS
        unmatched_yt_count = 0
        from src.fetcher import search_ddg
        
        for yt_topic in youtube_list:
            query_clean = re.sub(r'\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b', '', yt_topic, flags=re.IGNORECASE)
            query_clean = re.sub(r'\b\d{4}\b', '', query_clean)
            query_clean = re.sub(r'Editorial Discussion|Daily News Analysis|Current Affairs|UPSC|CSE|IAS', '', query_clean, flags=re.IGNORECASE)
            query_clean = re.sub(r'\s*\|\s*', ' ', query_clean)
            query_clean = re.sub(r'\s*#\w+', '', query_clean)
            query_clean = " ".join(query_clean.split()).strip()
            
            if not query_clean or len(query_clean) < 5:
                continue
                
            is_matched = False
            # Check Gemini match result
            for myt in matched_youtube_titles:
                if myt.lower() in yt_topic.lower() or yt_topic.lower() in myt.lower():
                    is_matched = True
                    break
                    
            # Programmatic verification check in selected raw articles
            if not is_matched:
                for art in curated_articles:
                    title_lower = art['title'].lower()
                    terms = [t for t in query_clean.lower().split() if len(t) > 3]
                    if terms and all(term in title_lower for term in terms[:3]):
                        is_matched = True
                        break
                        
            # Programmatic verification check in InsightsIAS topics
            if not is_matched:
                for topic in insights_list:
                    title_lower = topic['title'].lower()
                    terms = [t for t in query_clean.lower().split() if len(t) > 3]
                    if terms and all(term in title_lower for term in terms[:3]):
                        is_matched = True
                        break
                        
            if not is_matched:
                logger.info(f"YouTube topic '{yt_topic}' is unmatched. Running DDG web search for: '{query_clean}'...")
                search_results = search_ddg(query_clean + " UPSC")
                if not search_results:
                    search_results = search_ddg(query_clean)
                    
                if search_results:
                    summary = "\n\n".join(f"Source: {r['title']}\n{r['snippet']}" for r in search_results)
                    curated_articles.append({
                        'source': 'Web Search Curation',
                        'title': query_clean,
                        'link': search_results[0]['link'] if search_results[0]['link'] else 'https://www.google.com',
                        'summary': summary,
                        'published': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    unmatched_yt_count += 1
                    
        logger.info(f"Curation complete. Added {unmatched_insights_count} synthesized articles from InsightsIAS and {unmatched_yt_count} from Web Search. Total curated: {len(curated_articles)}")
        return curated_articles
        
    except Exception as e:
        logger.error(f"Error during curated news filtering: {e}")
        return filter_upsc_relevant_news(articles)

def analyze_all_news(articles, verification_data=None):
    """Filter news, fetch local PYQs, and run detailed analysis on the relevant articles."""
    relevant_articles = curate_news_with_verification(articles, verification_data)
    if not relevant_articles:
        logger.info("No UPSC relevant news found for today.")
        return []
        
    local_pyqs = load_local_pyqs()
    cards = []
    
    # Cap to 5 articles per day — stays well within the free API quota (1 filter call + 5 analysis calls = 6 total)
    max_cards = min(5, len(relevant_articles))
    logger.info(f"Generating UPSC study cards for {max_cards} articles...")
    
    for i in range(max_cards):
        if i > 0:
            time.sleep(8)  # 8-second pacing buffer to stay well under RPM and daily quota limits
        card = analyze_article(relevant_articles[i], local_pyqs)
        # Attach pre-classified topic if available from taxonomy filter
        if card.get('syllabus_topic') in ('GS Paper I/II/III: Current Affairs', '') and relevant_articles[i].get('_pre_classified'):
            card['syllabus_topic'] = relevant_articles[i]['_pre_classified']
        cards.append(card)
        
    return cards
