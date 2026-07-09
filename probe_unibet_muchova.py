from unibet_client import UnibetClient
import re

c = UnibetClient()
html = c.get_tennis_listing_html("/paris-tennis/wta/wimbledon-f")
for token in ("muchova", "gauff", "3363470"):
    print(token, token.lower() in html.lower())
for href in re.findall(r'href="(/paris-en-direct/[^"]+)"', html):
    if "much" in href.lower() or "gauff" in href.lower():
        print("live href", href)
for href in re.findall(r'href="(/paris-tennis/[^"]+)"', html):
    if "much" in href.lower() or "gauff" in href.lower():
        print("prematch href", href)
print("html links", len(c.list_tennis_events_from_html_links("/paris-tennis/wta/wimbledon-f")))
live_url = "/paris-en-direct/3363470/k-muchova-vs-c-gauff"
if live_url in html:
    print("direct live url found")
else:
    resp = c.session.get(c._url(live_url))
    print("live page status", resp.status_code)
