#!/usr/bin/env bash
# Remove benchmark-created Docker artifacts (containers / images / networks /
# build cache). Volumes are NOT touched (we don't create any).
#
# Usage:
#   scripts/cleanup_docker.sh           # dry-run, only prints what would happen
#   scripts/cleanup_docker.sh --yes     # actually delete
#   scripts/cleanup_docker.sh --yes --nuke-cache   # also drop full builder cache
#
# What "benchmark-created" means here:
#   - images named  e<n>-ls<m>-t<r>__<hash>-main   (per-trial Harbor image)
#   - images named  agent-runtime[:tag]
#   - networks named e<n>-ls<m>-t<r>__<hash>_default
#   - any container based on one of those images
# Other images / networks (bridge / host / none / non-benchmark repos) are
# left alone.

set -euo pipefail

DRY=1
NUKE_CACHE=0
for arg in "$@"; do
  case "$arg" in
    --yes|-y) DRY=0 ;;
    --nuke-cache) NUKE_CACHE=1 ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

run() {
  if (( DRY )); then
    echo "DRY: $*"
  else
    echo "RUN: $*"
    eval "$@"
  fi
}

bench_image_re='^(agent-runtime|e[0-9]+-ls[0-9]+-t[0-9]+__[a-z0-9]+-main)(:|$)'
bench_net_re='^e[0-9]+-ls[0-9]+-t[0-9]+__[a-z0-9]+_default$'

echo "=== before ==="
docker system df

echo
echo "=== 1. stop + remove benchmark containers ==="
mapfile -t cids < <(
  docker ps -a --format '{{.ID}} {{.Image}}' \
    | awk -v re="$bench_image_re" '$2 ~ re {print $1}'
)
if (( ${#cids[@]} )); then
  run "docker rm -f ${cids[*]}"
else
  echo "  no benchmark containers"
fi

echo
echo "=== 2. remove benchmark networks ==="
mapfile -t nets < <(
  docker network ls --format '{{.Name}}' | grep -E "$bench_net_re" || true
)
if (( ${#nets[@]} )); then
  run "docker network rm ${nets[*]}"
else
  echo "  no benchmark networks"
fi

echo
echo "=== 3. remove benchmark images ==="
mapfile -t imgs < <(
  docker images --format '{{.Repository}}:{{.Tag}}' \
    | grep -E "$bench_image_re" || true
)
if (( ${#imgs[@]} )); then
  # delete in chunks of 50 to keep the cmdline small
  for ((i=0; i<${#imgs[@]}; i+=50)); do
    chunk="${imgs[*]:i:50}"
    run "docker rmi -f $chunk"
  done
else
  echo "  no benchmark images"
fi

echo
echo "=== 4. drop dangling images + stopped containers ==="
run "docker container prune -f"
run "docker image prune -f"

if (( NUKE_CACHE )); then
  echo
  echo "=== 5. drop the full builder cache (--nuke-cache) ==="
  run "docker builder prune -af"
else
  echo
  echo "=== 5. builder cache: kept (pass --nuke-cache to also drop ~30GB) ==="
fi

echo
echo "=== after ==="
docker system df

if (( DRY )); then
  echo
  echo "(dry-run only -- re-run with --yes to actually delete)"
fi
