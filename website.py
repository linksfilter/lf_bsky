import csv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from dateutil import parser
from urllib.parse import urlparse
import re

POSTED_FILE = "posted.csv"
PARSED_FILE = "parsed.csv"
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
# Load parsed.csv into a dict by link
# -------------------------------
parsed_dict = {}
with open(PARSED_FILE, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        link = row["link"].strip()
        parsed_dict[link] = {
            "title": row.get("titel") or row.get("title") or link,
            "description": row.get("beschreibung") or row.get("description") or "",
            "thumb": row.get("thumb") or "",
            "date": row.get("date") or ""
        }

# -------------------------------
# Load last 50 links from posted.csv
# -------------------------------
with open(POSTED_FILE, encoding="utf-8") as f:
    all_links = [line.strip() for line in f.readlines() if line.strip()]

last50_links = all_links[-50:]

# -------------------------------
# Get metadata from parsed.csv
# -------------------------------
meta_list = []
for link in last50_links:
    meta = parsed_dict.get(link, {"title": link, "description": "", "thumb": "", "date": ""})
    meta["link"] = link
    meta_list.append(meta)

# -------------------------------
# TF-IDF using capitalized words
# -------------------------------
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
            return parser.parse(a.get("date", "1900-01-01"))
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

for cluster in clusters:
    main = cluster["main"]
    others = cluster["similar"]

    img_html = f'<img src="{main["thumb"]}" class="card-img-top" alt="">' if main["thumb"] else ""
    date_html = f'<div class="card-date">{format_date(main["date"])}</div>' if main.get("date") else ""

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
        date_o = f', {format_date(o["date"])}' if o.get("date") else ""
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
