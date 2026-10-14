import os, re, subprocess, sys

FMHY = sys.argv[1]
PAGE = sys.argv[2]
OUT = sys.argv[3]
HOURS = int(os.environ.get("LOOKBACK_HOURS", "25"))

URL_RE = re.compile(r'https?://[^\s)\]>"\'`]+')

def norm(u):
    u = re.sub(r'^https?://', '', u.strip())
    return u.rstrip('/.,;').lower()

def clean(s):
    return re.sub(r'[\u200b-\u200f\u2060\ufeff\u00ad]', '', s).strip()

def git(*a):
    return subprocess.run(["git", "-C", FMHY, *a], capture_output=True, text=True).stdout

base = git("rev-list", "-1", f"--before={HOURS} hours ago", "HEAD").strip()
if not base:
    print("no base commit found")
    open(OUT, "w").close()
    sys.exit(0)

diff = git("diff", base, "HEAD", "--", "docs/*.md")
plus, minus = {}, {}
for line in diff.splitlines():
    if line.startswith("+++") or line.startswith("---"):
        continue
    if line.startswith("+"):
        for u in URL_RE.findall(line):
            plus[norm(u)] = u
    elif line.startswith("-"):
        for u in URL_RE.findall(line):
            minus[norm(u)] = u

added = set(plus) - set(minus)
removed = set(minus) - set(plus)

html = open(PAGE, encoding="utf-8").read()
page = {s.rstrip('/').lower() for s in re.findall(r'"((?:[a-z0-9-]+\.)+[a-z]{2,}(?:[/:][^"]*)?)"', html, re.I)}

new_links = sorted(added - page)
dead_links = sorted(removed & page)

where = {}
for root, _, files in os.walk(os.path.join(FMHY, "docs")):
    for f in files:
        if not f.endswith(".md"):
            continue
        heading = ""
        for line in open(os.path.join(root, f), encoding="utf-8", errors="ignore"):
            if line.startswith("#"):
                heading = line.strip("# \n")
            for u in URL_RE.findall(line):
                n = norm(u)
                if n in added and n not in where:
                    name = re.search(r'\[([^\]]+)\]\(' + re.escape(u), line)
                    where[n] = (f[:-3], clean(heading), clean(name.group(1)) if name else "")

if not new_links and not dead_links:
    print("nothing to suggest")
    open(OUT, "w").close()
    sys.exit(0)

head = git("rev-parse", "--short", "HEAD").strip()
out = [f"Changes in fmhy/edit from {base[:7]} to {head}.", ""]
out.append(f"Suggested additions: {len(new_links)}")
out.append("")
for n in new_links:
    page_name, heading, name = where.get(n, ("", "", ""))
    shown = re.sub(r'^https?://', '', plus[n]).rstrip('/')
    out.append(f"- [ ] ADD `{shown}` name: {name or 'unknown'} section: {page_name} / {heading}")
out.append("")
out.append(f"Suggested removals (on this site, removed from FMHY): {len(dead_links)}")
out.append("")
for n in dead_links:
    out.append(f"- [ ] REMOVE `{re.sub(r'^https?://', '', minus[n]).rstrip('/')}`")
body = "\n".join(out)
if len(body) > 60000:
    body = body[:60000] + "\n\nTruncated."
open(OUT, "w", encoding="utf-8").write(body)
print(f"{len(new_links)} additions, {len(dead_links)} removals")
