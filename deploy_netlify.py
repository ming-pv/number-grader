"""Deploy grader.html to Netlify via the Deploy API (zip upload).

Usage:
    python deploy_netlify.py

First run prompts for your Netlify Personal Access Token (hidden input,
get one at https://app.netlify.com/user/applications) and caches it in
.netlify_token (gitignored) so you won't be asked again on this machine.
"""

import io, os, sys, zipfile, urllib.request, urllib.error, json, string

SITE_SLUG  = "serene-rugelach-769e50"   # site name / slug from the Netlify URL
FILES      = ["index.html"]
TOKEN_FILE = ".netlify_token"
GITIGNORE  = ".gitignore"
PRINTABLE  = set(string.ascii_letters + string.digits + "-_.")

def ensure_gitignored():
    line = TOKEN_FILE + "\n"
    existing = ""
    if os.path.exists(GITIGNORE):
        existing = open(GITIGNORE, encoding="utf-8").read()
    if TOKEN_FILE not in existing:
        with open(GITIGNORE, "a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write(line)

def sane_token(t):
    # A real Netlify PAT is a long alnum/dash string. Reject anything that
    # looks like a mangled paste (control chars, too short) so we fail loud
    # instead of caching garbage and silently 400-ing on every API call.
    t = t.strip()
    return len(t) >= 20 and all(c in PRINTABLE for c in t)

def get_token():
    if os.path.exists(TOKEN_FILE):
        t = open(TOKEN_FILE, encoding="utf-8").read().strip()
        if sane_token(t):
            return t
        print(f"Cached {TOKEN_FILE} looks invalid/corrupted - ignoring it and re-prompting.")

    # Plain input(), not getpass: some terminal/PTY setups mangle getpass's
    # hidden-input handling into control characters instead of the real
    # paste. The token is short-lived/revocable, so visible input is an
    # acceptable tradeoff for reliability.
    t = input("Netlify Personal Access Token (visible input, from "
               "https://app.netlify.com/user/applications): ").strip()
    if not sane_token(t):
        print(f"That doesn't look like a valid token (got {len(t)} chars, "
              f"repr={t!r}). Aborting without caching it.")
        sys.exit(1)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(t)
    ensure_gitignored()
    print(f"Token saved to {TOKEN_FILE} (added to .gitignore) for next time.")
    return t

def api_get(token, path):
    req = urllib.request.Request(
        f"https://api.netlify.com/api/v1{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def resolve_site_id(token):
    print(f"Looking up site '{SITE_SLUG}'…")
    try:
        site = api_get(token, f"/sites/{SITE_SLUG}")
        print(f"Found via direct lookup: {site.get('name')} (id: {site['id']})")
        return site["id"]
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        if e.code == 401:
            print(f"Token rejected (401 Unauthorized): {body}\n"
                  f"Delete .netlify_token and re-run with a fresh token.")
            sys.exit(1)
        print(f"Direct lookup failed ({e.code}: {body}), listing all accessible sites…")

    try:
        sites = api_get(token, "/sites")
    except urllib.error.HTTPError as e:
        print(f"Listing sites also failed - HTTP {e.code}: {e.read().decode(errors='replace')}")
        sys.exit(1)
    if not sites:
        print("Your token can't see ANY sites. Check the token was created under the "
              "same Netlify account/team that owns this site.")
        sys.exit(1)

    print(f"{len(sites)} site(s) visible to this token:")
    for s in sites:
        print(f"  name={s.get('name'):40s} id={s['id']}  url={s.get('ssl_url') or s.get('url')}")

    match = next(
        (s for s in sites
         if s.get("name") == SITE_SLUG
         or s.get("id") == SITE_SLUG
         or SITE_SLUG in (s.get("ssl_url") or "")
         or SITE_SLUG in (s.get("url") or "")),
        None
    )
    if not match:
        print(f"\nNone of the above match '{SITE_SLUG}'. Copy the correct `id` from the "
              f"list above and hardcode it as SITE_SLUG in this script, or check you're "
              f"using the right Netlify account.")
        sys.exit(1)
    print(f"Matched: {match.get('name')} (id: {match['id']})")
    return match["id"]

def main():
    token = get_token()
    site_id = resolve_site_id(token)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in FILES:
            zf.write(f)
    zip_data = buf.getvalue()
    print(f"Zip size: {len(zip_data):,} bytes ({', '.join(FILES)})")

    print("Uploading to Netlify…")
    req = urllib.request.Request(
        f"https://api.netlify.com/api/v1/sites/{site_id}/deploys",
        data=zip_data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/zip"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read())
        print(f"Deploy state : {body.get('state', '?')}")
        print(f"Live site    : {body.get('ssl_url') or body.get('url') or f'https://{SITE_SLUG}.netlify.app'}")
    except urllib.error.HTTPError as e:
        print(f"Deploy failed — HTTP {e.code}: {e.read().decode()}")
        sys.exit(1)

if __name__ == "__main__":
    main()
