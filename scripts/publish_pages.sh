#!/usr/bin/env bash
# Publish the server-less site to GitHub Pages (branch gh-pages).
# Run from the repository root:  bash scripts/publish_pages.sh        (add --no-llm to skip the gpt-oss wording)
set -euo pipefail
uv run python -m src.atlas.export_static "$@"
(cd web && npm install --no-audit --no-fund && npm run build:pages)
remote=$(git remote get-url origin)
tmp=$(mktemp -d)
cp -r web/dist-pages/. "$tmp"
cd "$tmp"
git init -q -b gh-pages
git add -A
git -c user.name="${GIT_AUTHOR_NAME:-atlas}" -c user.email="${GIT_AUTHOR_EMAIL:-atlas@users.noreply.github.com}" commit -q -m "Publish site"
git push -q -f "$remote" gh-pages
echo "Pushed. The site is served from the gh-pages branch."
