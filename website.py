import pandas as pd
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

    # Try to fetch OG image
    try:
        if "meta_img" in article.__dict__ and article.meta_img:
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
# Build Bootstrap HTML
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
.card-img-top {
    object-fit: cover;
    height: 180px;
}
</style>

</head>
<body class="bg-light">

<div class="container py-5">
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
    <div class="col-md-4">
      <div class="card shadow-sm h-100">
        {img_html}
        <div class="card-body">
          <h5 class="card-title">{title}</h5>
          <p class="card-text">{desc}</p>
          <a href="{link}" class="btn btn-primary" target="_blank">Open Link</a>
        </div>
      </div>
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

print("Website generated")
