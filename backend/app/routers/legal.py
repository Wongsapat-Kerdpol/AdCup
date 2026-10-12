"""[PERSON 3] Plain Terms of Service / Privacy Policy pages.

TikTok's developer portal requires public URLs for both before an app (even a Sandbox) can be
saved. Served by the backend so they're reachable through the same https tunnel as the OAuth
callback, e.g. https://<ngrok-domain>/legal/terms.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/legal", tags=["legal (Person 3)"], include_in_schema=False)

_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title} · AdCup</title>
<style>body{{font-family:system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px;line-height:1.6;
color:#1c1c1c}}h1{{font-size:1.6rem}}h2{{font-size:1.1rem;margin-top:1.6em}}</style></head>
<body><h1>{title}</h1><p><em>AdCup is a university course project (KMITL). Last updated October 2026.</em></p>{body}</body></html>"""

_TERMS = """
<h2>The service</h2>
<p>AdCup connects brands that run promotional campaigns with creators who post original videos.
Creators are paid from a campaign's budget according to the views their approved videos receive.
No real money is transferred: payments and withdrawals in AdCup are simulated.</p>
<h2>Your account</h2>
<p>You are responsible for the content you submit. Submitted videos must be your own original work
and posted on an account you have connected. AdCup may reject submissions that do not meet a
campaign's requirements or these terms.</p>
<h2>Connected accounts</h2>
<p>Connecting YouTube or TikTok is optional and only needed to submit videos from that platform.
You can disconnect at any time in Settings.</p>
<h2>Changes</h2>
<p>As a course project, the service may change or be shut down at any time.</p>
"""

_PRIVACY = """
<h2>What we collect</h2>
<p>Your name, email address and password (stored only as a secure hash). If you connect a
platform account we store its account id and display name, the access tokens needed to read your
videos' statistics, and, for videos you submit, their title, publish date and view count.</p>
<h2>How we use it</h2>
<p>Only to run AdCup: confirm that a submitted video belongs to you, track its views, and calculate
earnings. Tokens are never shown in the app or shared with anyone. We only request read-only access
and never post, edit or delete anything on your accounts.</p>
<h2>Your choices</h2>
<p>Disconnect a platform in Settings at any time; this deletes its stored tokens and revokes our
access with that platform. You can also revoke access from the platform's own app settings.</p>
<h2>Contact</h2>
<p>This is a student project; contact the AdCup team through your course instructor.</p>
"""


@router.get("/terms", response_class=HTMLResponse)
def terms():
    return _PAGE.format(title="Terms of Service", body=_TERMS)


@router.get("/privacy", response_class=HTMLResponse)
def privacy():
    return _PAGE.format(title="Privacy Policy", body=_PRIVACY)
