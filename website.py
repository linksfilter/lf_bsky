import csv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from dateutil import parser
from urllib.parse import urlparse
import re

POSTED_FILE = "posted.csv"
PARSED_FILE = "parsed.csv"
STOPWORDS_FILE = "stopwords.csv"
OUTPUT_FILE = "docs/index.html"
SIM_THRESHOLD = 0.2  # similarity threshold for related links

# -------------------------------
# Load stopwords from stopwords.csv
# -------------------------------
stopwords = []

with open(STOPWORDS_FILE, encoding="utf-8") as f:
    for line in f:
        w = line.strip()
        if w:
            stopwords.append(w)

def preprocess_stopwords(stopwords):
    # lowercase all stopwords to match the vectorizer
    return [w.lower() for w in stopwords]

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
# Extract top keywords from texts using the same TF-IDF model
# -------------------------------
def top_keywords(texts, vectorizer, top_n=3):
    if not texts:
        return []
    tfidf = vectorizer.transform(texts)
    summed = tfidf.sum(axis=0)        # sum scores across all cluster docs
    words = vectorizer.get_feature_names_out()
    scores = [(words[i], summed[0, i]) for i in range(len(words))]
    scores = sorted(scores, key=lambda x: x[1], reverse=True)
    return [w for w, s in scores[:top_n]]

def get_domain(link):
    domain_long = urlparse(link).netloc
    # Keep only the last two parts (example.com)
    return '.'.join(domain_long.split('.')[-2:])

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

last50_links = reversed(all_links[-50:])

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
vectorizer = TfidfVectorizer(
    stop_words=preprocess_stopwords(stopwords)
)
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

    # compute top keywords for cluster
    cluster_texts = [
        capitalized_words(a["title"] + " " + a["description"])
        for a in cluster_articles
    ]
    keywords = top_keywords(cluster_texts, vectorizer, top_n=3)

    clusters.append({"main": main_article, "similar": other_articles, "keywords": keywords})

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

:root {
    --primary-color: #D95BF5; /* vibrant purple-pink */
}

h1,
.card-title,
.similar-links a,
.card-img-top {
    color: var(--primary-color);
    /* For images, you can add a subtle border or shadow in this color if needed */
}

/* Optional: hover effect */
.card-link-wrapper:hover .card-title,
.similar-links a:hover {
    text-decoration: underline;
    color: #F57BBF; /* slightly lighter pink for hover */
}

.card-link-wrapper {
    display: block;
    text-decoration: none;
    color: inherit;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
    margin-bottom: 1rem;
    border-radius: 0.25rem;
}

.card-link-wrapper:hover {
    cursor: pointer;
}

.card-img-top {
    width: 100%;
    aspect-ratio: 2 / 1; /* 3:2 ratio */
    object-fit: cover;    /* crop or fill to fit */
    border-radius: 0.25rem 0.25rem 0 0;
}

.card-body {
    padding: 1rem;
}

.card-title {
    margin-bottom: 0.5rem;
    font-size: 1.25rem;
    text-decoration: none;
}

.card-link-wrapper:hover .card-title {
    text-decoration: underline;
}

.card-date {
    font-size: 0.85rem;
    color: gray;
    margin-bottom: 0.5rem;
}

.card-img-wrapper {
    position: relative;
    width: 100%;
    padding-top: 50%; /* 3:2 aspect ratio */
    overflow: hidden;
    border-radius: 0.25rem 0.25rem 0 0;
    filter: saturate(25%); /* slight desaturation */
}

.card-img-wrapper img {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
}

/* Tint overlay */
.card-img-wrapper::after {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: var(--primary-color);
    opacity: 0.25; /* adjust intensity of tint */
    pointer-events: none; /* so the link is still clickable */
}

.keywords {
    font-size: 0.85rem;
    color: #444;
    margin-bottom: 0.5rem;
}

.similar-links a {
    display: block;
    font-size: 0.9rem;
    margin-bottom: 0.25rem;
    text-decoration: none;
    color: #007bff;
}

.similar-links a:hover {
    text-decoration: underline;
}
</style>
</head>
<body class="bg-light">
<div class="container py-5" style="max-width: 800px;">
<h1 class="mb-4">LinksFilter</h1>
<div class="row g-3"> <!-- g-3 adds spacing between cards -->
"""

for cluster in clusters:
    main = cluster["main"]
    others = cluster["similar"]

    img_html = f'<img src="{main["thumb"]}" class="card-img-top" alt="">' if main["thumb"] else ""
    date_str = format_date(main.get("date", ""))

    # Domain and date
    main_domain = get_domain(main["link"])
    if main_domain and date_str:
        meta_html = f'<div class="card-date">{main_domain} | {date_str}</div>'
    elif main_domain:
        meta_html = f'<div class="card-date">{main_domain}</div>'
    elif date_str:
        meta_html = f'<div class="card-date">{date_str}</div>'
    else:
        meta_html = ""

    # Determine column width
    if len(others) == 0:
        col_class = "col-md-6"  # Half width for single cards
    else:
        col_class = "col-12"    # Full width for collection cards

    # Keywords
    kw_html = ""
    if cluster["keywords"]:
        kw_html = '<div class="keywords">' + " • ".join(cluster["keywords"]) + "</div>"

    html += f"""
    <div class="{col_class}">
    <a href="{main['link']}" target="_blank" class="card-link-wrapper">
      <div class="card shadow-sm mb-3">
        <div class="card-img-wrapper">
        {img_html}
        </div>
        <div class="card-body">
          <h4 class="card-title">{main['title']}</h4>
          {meta_html}
          <p class="card-text">{main['description']}</p>
          {kw_html}
          <div class="similar-links">
    """

    for o in others:
        domain_o = get_domain(o["link"])
        date_o = f', {format_date(o["date"])}' if o.get("date") else ""
        html += f'<a href="{o["link"]}" target="_blank">{o["title"]} ({domain_o}{date_o})</a>'

    html += """
            </div>
        </div>
        </div>
    </a>
    </div>
    """

html += """
</div>
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
