import requests
from newspaper import Article, Config

INPUT_FILE = "posted.csv"
OUTPUT_FILE = "docs/index.html"


# -----------------------------------------------------
# Simple metadata enrichment using Newspaper3k
# -----------------------------------------------------
def enrich(link):
    config = Config()
    config.request_timeout = 10

    try:
        article = Article(link, config=config)
        article.download()
        article.parse()
    except:
        return {
            "title": link,
            "description": "",
            "thumb": "",
            "link": link
        }

    title = article.title or link
    desc = article.meta_description or ""

    thumb = ""
    try:
        if getattr(article, "meta_img", ""):
            thumb = article.meta_img
    except:
        thumb = ""

    return {
        "title": title,
        "description": desc,
        "thumb": thumb,
        "link": link
    }


# -----------------------------------------------------
# Load the first 10 links
# -----------------------------------------------------
with open(INPUT_FILE) as f:
    all_links = [line.strip() for line in f.readlines() if line.strip()]

links10 = all_links[:10]

# Enrich each link
items = [enrich(link) for link in links10]


# -----------------------------------------------------
# Build Bootstrap HTML (single column, big cards)
# Whole card is clickable
# -----------------------------------------------------
html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Recent Links</title>

<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">

<style>
.card {
    transition: transform 0.1s ease;
    border-radius: 12px;
}
.card:hover {
    transform: scale(1.01);
}
.card-img-top {
    object-fit: cover;
    height: 260px; /* larger image */
    border-radius: 12px 12px 0 0;
}
.card a {
    text-decoration: none;
    color: inherit;
}
</style>

</head>
<body class="bg-light">

<div class="container py-5" style="max-width: 700px;">
<h1 class="mb-4">Most Recent Links</h1>
<div class="row g-4">
"""

for item in items:
    title = item["title"]
    desc = item["description"]
    link = item["link"]
    thumb = item["thumb"]

    img_html = f'<img src="{thumb}" class="card-img-top" alt="">' if thumb else ""

    html += f"""
    <div class="col-12">
      <a href="{link}" target="_blank">
        <div class="card shadow-sm">
          {img_html}
          <div class="card-body">
            <h4 class="card-title">{title}</h4>
            <p class="card-text">{desc}</p>
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

# -----------------------------------------------------
# Save HTML file
# -----------------------------------------------------
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(html)

print("Website generated:", OUTPUT_FILE)
