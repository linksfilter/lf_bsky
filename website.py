# Sort links_df by createdAt if available, else just take the order they appear
recent_links = links_df.sort_values(by="createdAt", ascending=False).head(10)

# Simple HTML page
html = "<html><body>\n"
html += "<h1>Most Recent Links</h1>\n"
html += "<ul>\n"

for _, row in recent_links.iterrows():
    link = row['link']
    title = row['titel'] if row['titel'] else link
    html += f'<li><a href="{link}">{title}</a></li>\n'

html += "</ul>\n</body></html>"

# Write to GitHub Pages folder (must exist in your repo)
# Example: docs/index.html  → served at yourusername.github.io/reponame
with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write(html)
