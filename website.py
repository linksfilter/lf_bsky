import pandas as pd
import requests
from pathlib import Path

# -----------------------------
# Paths
# -----------------------------
LINKS_CSV = "links.csv"        # file containing your last 10 links
OUTPUT_HTML = "index.html"

# -----------------------------
# Enrich links function
# -----------------------------
def enrich_link(link):
    """
    Fetch basic metadata for a link: title, description, and image (if any)
    Uses OpenGraph or defaults.
    """
    try:
        resp = requests.get(link, timeout=5)
        resp.raise_for_status()
        html = resp.text

        # Simple title extraction
        import re
        title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
        title = title_match.group(1) if title_match else link

        # Simple description extraction from meta tag
        desc_match = re.search(r'<meta name="description" content="(.*?)"', html, re.IGNORECASE)
        description = desc_match.group(1) if desc_match else title

        # Try to find og:image
        img_match = re.search(r'<meta property="og:image" content="(.*?)"', html, re.IGNORECASE)
        image = img_match.group(1) if img_match else None

        return title, description, image
    except:
        return link, link, None

# -----------------------------
# Load links
# -----------------------------
df = pd.read_csv(LINKS_CSV, header=None, names=["link"])
df = df.tail(10)  # last 10 links

# Enrich links
enriched = []
for link in df["link"]:
    title, desc, image = enrich_link(link)
    enriched.append({"link": link, "title": title, "desc": desc, "image": image})

# -----------------------------
# Generate HTML
# -----------------------------
html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Links</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
  body {
    background-color: #f8f9fa;
    padding: 2rem;
  }
  .link-card {
    display: block;
    width: 50%;
    margin: 1rem auto;
    aspect-ratio: 3 / 2;
    overflow: hidden;
    text-decoration: none;
    color: inherit;
  }
  .link-card .card-img-top {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .link-card .card-body {
    padding: 0.5rem;
  }
  @media (max-width: 768px) {
    .link-card {
      width: 90%;
    }
  }
</style>
</head>
<body>
<h1 class="text-center mb-4">Latest Links</h1>
"""

# Add cards
for item in enriched:
    img_html = f'<img src="{item["image"]}" class="card-img-top">' if item["image"] else ""
    html += f"""
<a href="{item['link']}" target="_blank" class="link-card">
  <div class="card shadow-sm">
    {img_html}
    <div class="card-body">
      <h4 class="card-title">{item['title']}</h4>
      <p class="card-text">{item['desc']}</p>
    </div>
  </div>
</a>
"""

html += """
</body>
</html>
"""

# -----------------------------
# Save HTML
# -----------------------------
Path(OUTPUT_HTML).write_text(html, encoding="utf-8")
print(f"HTML page generated at {OUTPUT_HTML}")
