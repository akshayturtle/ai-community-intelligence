#!/bin/bash
# ============================================================
# Community Mind Mirror — Full Scraper Run
# Target: 10,000+ users, 500+ videos
# ============================================================
# Usage:
#   cd community-mind-mirror
#   chmod +x run_scrapers.sh
#   ./run_scrapers.sh           # Run all scrapers
#   ./run_scrapers.sh reddit    # Run only reddit
#   ./run_scrapers.sh youtube   # Run only youtube
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/scrape_${TIMESTAMP}.log"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo -e "$msg" | tee -a "$LOG_FILE"
}

log_header() {
    echo "" | tee -a "$LOG_FILE"
    echo "============================================================" | tee -a "$LOG_FILE"
    log "${CYAN}$1${NC}"
    echo "============================================================" | tee -a "$LOG_FILE"
}

run_scraper() {
    local name=$1
    local start_time=$(date +%s)

    log_header "Running $name scraper"

    if python main.py --scraper "$name" 2>&1 | tee -a "$LOG_FILE"; then
        local end_time=$(date +%s)
        local duration=$(( end_time - start_time ))
        local minutes=$(( duration / 60 ))
        local seconds=$(( duration % 60 ))
        log "${GREEN}✓ $name completed in ${minutes}m ${seconds}s${NC}"
    else
        log "${RED}✗ $name FAILED (exit code $?)${NC}"
    fi
}

print_summary() {
    log_header "Database Summary"
    python main.py --summary 2>&1 | tee -a "$LOG_FILE"
}

# ============================================================
# Main
# ============================================================

log_header "Community Mind Mirror — Scraper Run"
log "Log file: $LOG_FILE"
log "Target: 10,000+ users, 500+ YouTube videos"
echo ""

# Print current state
log "${YELLOW}Current database state:${NC}"
print_summary

SCRAPER_TARGET="${1:-all}"

TOTAL_START=$(date +%s)

if [ "$SCRAPER_TARGET" = "all" ]; then
    log_header "Running ALL scrapers sequentially"
    log "Order: reddit → hn → youtube → news → arxiv → jobs"
    echo ""

    # Reddit first — biggest user source (50 subreddits × 500 posts each)
    # Expected: ~5,000-8,000 new users from expanded subreddit list
    run_scraper "reddit"

    # Hacker News — second biggest user source
    # Expected: ~1,000-3,000 new users
    run_scraper "hn"

    # YouTube — 31 channels × 20 videos = 620 videos + commenters
    # Expected: 500+ videos, ~500-1,000 commenter users
    run_scraper "youtube"

    # News, ArXiv, Jobs — these add news_events, not users
    run_scraper "news"
    run_scraper "arxiv"
    run_scraper "jobs"
else
    run_scraper "$SCRAPER_TARGET"
fi


TOTAL_END=$(date +%s)
TOTAL_DURATION=$(( TOTAL_END - TOTAL_START ))
TOTAL_MIN=$(( TOTAL_DURATION / 60 ))
TOTAL_SEC=$(( TOTAL_DURATION % 60 ))

echo ""
log_header "Final Database State"
print_summary

log "${GREEN}All done! Total time: ${TOTAL_MIN}m ${TOTAL_SEC}s${NC}"
log "Full log: $LOG_FILE"
echo ""
echo "Next steps:"
echo "  python main.py --processor all    # Run LLM processors on new data"
