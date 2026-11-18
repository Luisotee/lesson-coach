#!/usr/bin/env bash
# Writes the delivery zip: a fresh `git clone` of this repo, so it holds the committed tree
# and the full history (.git), and nothing local (no .env, node_modules, .venv, dist, caches).
#
#   scripts/zip.sh                 # ../lesson-coach.zip, from the checked-out branch
#   scripts/zip.sh out.zip [ref]   # another path, or another branch or tag
set -euo pipefail

root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
out="$(realpath -m "${1:-$root/../lesson-coach.zip}")"
ref="${2:-$(git -C "$root" rev-parse --abbrev-ref HEAD)}"   # "HEAD" when detached
sha="$(git -C "$root" rev-parse --verify "$ref^{commit}")"
command -v zip >/dev/null || { echo "zip is not installed" >&2; exit 1; }
[[ -z "$(git -C "$root" status --porcelain)" ]] ||
  echo "note: uncommitted changes are not in the zip (it is built from commits only)" >&2

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
# --no-local copies objects like a remote clone would (no hard links into this repo).
# Cloning by commit, not --branch, also works for a detached HEAD, a tag or a remote ref.
git clone -q --no-local --no-checkout "$root" "$work/lesson-coach"
if [[ "$ref" != HEAD ]] && git -C "$root" show-ref -q --verify "refs/heads/$ref"; then
  git -C "$work/lesson-coach" checkout -q -B "$ref" "$sha"   # keep the branch name
else
  git -C "$work/lesson-coach" checkout -q --detach "$sha"
fi
git -C "$work/lesson-coach" remote remove origin   # don't ship this machine's path
# Only the chosen ref: drop any other local branch the clone made, then unreachable objects.
current="$(git -C "$work/lesson-coach" symbolic-ref -q --short HEAD || true)"
git -C "$work/lesson-coach" for-each-ref --format='%(refname:short)' refs/heads |
  while read -r b; do [[ "$b" == "$current" ]] || git -C "$work/lesson-coach" branch -q -D "$b"; done
git -C "$work/lesson-coach" reflog expire --expire=now --all
git -C "$work/lesson-coach" gc -q --prune=now

rm -f "$out"
(cd "$work" && zip -qr -X "$out" lesson-coach)
echo "wrote $out ($(du -h "$out" | cut -f1), $(git -C "$work/lesson-coach" rev-parse --short HEAD), $ref)"
