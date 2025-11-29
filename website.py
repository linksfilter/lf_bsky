import requests
from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from dateutil import parser
import re
from urllib.parse import urlparse

INPUT_FILE = "posted.csv"
OUTPUT_FILE = "docs/index.html"
SIM_THRESHOLD = 0.1  # similarity threshold for related links

# -------------------------------
# Format date to DD.MM.YYYY
# -------------------------------
def format_date(date_str):
    if not date_str:
        return ""
    try:
        dt = parser.parse(date_str)
        return dt.strftime("%d.%m.%Y")
    except:
        return date_str

# -------------------------------
# Extract capitalized words (German-friendly)
# -------------------------------
def capitalized_words(text):
    words = re.findall(r'\b[A-ZÄÖÜ][a-zäöüß]+\b', text)
    return " ".join(words)

# -------------------------------
# Fetch title, description, date
# -------------------------------
def fetch_meta(link):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(link, headers=headers, timeout=10)
        resp.raise_for_status()
        html = resp.text
    except:
        return {"link": link, "title": link, "description": "", "date": ""}

    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else link

    desc = ""
    for attr in [{"name": "description"}, {"property": "og:description"}, {"name": "twitter:description"}]:
        tag = soup.find("meta", attrs=attr)
        if tag and tag.get("content"):
            desc = tag["content"]
            break

    date = ""
    for attr in [{"property": "article:published_time"}, {"name": "pubdate"}, {"name": "date"}]:
        tag = soup.find("meta", attrs=attr)
        if tag and tag.get("content"):
            date = format_date(tag["content"])
            break

    return {"link": link, "title": title, "description": desc, "date": date}

# -------------------------------
# Enrich full metadata (for HTML)
# -------------------------------
def enrich_full(link):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(link, headers=headers, timeout=10)
        resp.raise_for_status()
        html = resp.text
    except:
        return {"link": link, "title": link, "description": "", "thumb": "", "date": ""}

    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else link

    desc = ""
    for attr in [{"name": "description"}, {"property": "og:description"}, {"name": "twitter:description"}]:
        tag = soup.find("meta", attrs=attr)
        if tag and tag.get("content"):
            desc = tag["content"]
            break

    thumb = ""
    for attr in [{"property": "og:image"}, {"name": "twitter:image"}]:
        tag = soup.find("meta", attrs=attr)
        if tag and tag.get("content"):
            thumb = tag["content"]
            break

    date = ""
    for attr in [{"property": "article:published_time"}, {"name": "pubdate"}, {"name": "date"}]:
        tag = soup.find("meta", attrs=attr)
        if tag and tag.get("content"):
            date = format_date(tag["content"])
            break

    return {"link": link, "title": title, "description": desc, "thumb": thumb, "date": date}

# -------------------------------
# Load last 50 links
# -------------------------------
with open(INPUT_FILE) as f:
    all_links = [line.strip() for line in f.readlines() if line.strip()]

last50_links = all_links[-50:]

# -------------------------------
# Fetch metadata for similarity
# -------------------------------
meta_list = [fetch_meta(link) for link in last50_links]

# TF-IDF using capitalized words
texts = [capitalized_words(m["title"] + " " + m["description"]) for m in meta_list]
vectorizer = TfidfVectorizer()
tfidf_matrix = vectorizer.fit_transform(texts)
cos_sim = cosine_similarity(tfidf_matrix)

# -------------------------------
# Greedy clustering: pick 10 main links (most recent as main)
# -------------------------------
remaining_indices = list(range(len(meta_list)))
clusters = []

for _ in range(10):
    if not remaining_indices:
        break

    seed_idx = remaining_indices[0]
    seed = meta_list[seed_idx]

    sim_scores = cos_sim[seed_idx]
    similar_indices = [
        idx for idx in remaining_indices
        if idx != seed_idx and sim_scores[idx] > SIM_THRESHOLD
    ]
    similar_links = [meta_list[idx] for idx in similar_indices]

    cluster_articles = [seed] + similar_links

    # Sort cluster by published date descending
    def date_key(a):
        try:
            return parser.parse(a["date"])
        except:
            return parser.parse("1900-01-01")
    cluster_articles.sort(key=date_key, reverse=True)
    main_article = cluster_articles[0]
    other_articles = cluster_articles[1:]

    clusters.append({"main": main_article, "similar": other_articles})

    # Remove processed indices
    to_remove = [remaining_indices.index(meta_list.index(a)) for a in cluster_articles]
    remaining_indices = [idx for i, idx in enumerate(remaining_indices) if i not in to_remove]

# -------------------------------
# Enrich main + similar links for HTML
# -------------------------------
final_clusters = []
for cluster in clusters:
    all_articles = [cluster["main"]] + cluster["similar"]
    enriched = [enrich_full(a["link"]) for a in all_articles]
    final_clusters.append(enriched)

# -------------------------------
# Generate HTML
# -------------------------------
html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LinksFilter</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
.card { margin-bottom: 1rem; border-radius: 12px; }
.card-img-top { object-fit: cover; height: 200px; border-radius: 12px 12px 0 0; }
.similar-links a { display: block; font-size: 0.9rem; margin-bottom: 0.25rem; }
.card-date { font-size: 0.85rem; color: gray; margin-bottom: 0.5rem; }
.domain { font-size: 0.8rem; color: #777; margin-left: 0.3rem; }
</style>
</head>
<body class="bg-light">
<div class="container py-5" style="max-width: 800px;">
<h1 class="mb-4">LinksFilter</h1>
"""

for cluster in final_clusters:
    main = cluster[0]
    others = cluster[1:]

    img_html = f'<img src="{main["thumb"]}" class="card-img-top" alt="">' if main["thumb"] else ""
    date_html = f'<div class="card-date">{main["date"]}</div>' if main["date"] else ""

    html += f"""
    <div class="card shadow-sm">
      {img_html}
      <div class="card-body">
        <h4 class="card-title"><a href="{main["link"]}" target="_blank">{main["title"]}</a></h4>
        {date_html}
        <p class="card-text">{main["description"]}</p>
        <div class="similar-links">
    """

    for o in others:
        domain_long = urlparse(o["link"]).netloc
        domain = '.'.join(domain_long.split('.')[-2:])
        date_o = f', {o["date"]}' if o["date"] else ""
        html += f'<a href="{o["link"]}" target="_blank">{o["title"]} ({domain}{date_o})</a>'

    html += """
        </div>
      </div>
    </div>
    """

html += """
</div>
</body>
</html>
"""

# -------------------------------
# Save HTML
# -------------------------------
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(html)

print("Website generated:", OUTPUT_FILE)
