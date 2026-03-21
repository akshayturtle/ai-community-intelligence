# Community Mind Mirror — Registration Guide

## Summary

| # | Source | Registration Needed? | Cost | Time to Set Up |
|---|--------|---------------------|------|----------------|
| 1 | Reddit (.rss) | NO | Free | 0 min |
| 2 | Hacker News API | NO | Free | 0 min |
| 3 | Hacker News Algolia Search | NO | Free | 0 min |
| 4 | YouTube Data API v3 | YES — Google Cloud | Free (10K units/day) | 10 min |
| 5 | YouTube RSS | NO | Free | 0 min |
| 6 | YouTube Transcripts | NO (Python library) | Free | 0 min |
| 7 | News RSS Feeds | NO | Free | 0 min |
| 8 | ArXiv API | NO | Free | 0 min |
| 9 | JobSpy | NO (Python library) | Free | 0 min |

**Only ONE registration needed: Google Cloud for YouTube API.**

---

## Registration Step-by-Step

### YouTube Data API v3 (the only one that needs registration)

1. Go to **https://console.cloud.google.com**
2. Sign in with your Google account
3. Click **"Select a Project"** (top bar) → **"New Project"**
4. Name it `community-mind-mirror` → Click **Create**
5. Make sure the new project is selected in the top bar
6. Go to **APIs & Services → Library** (left sidebar)
7. Search for **"YouTube Data API v3"**
8. Click on it → Click **"Enable"**
9. Go to **APIs & Services → Credentials** (left sidebar)
10. Click **"+ Create Credentials"** → Select **"API Key"**
11. Copy the API key — this is your `YOUTUBE_API_KEY`
12. **Optional but recommended:** Click "Edit API key" → Under "API restrictions" → Select "Restrict key" → Choose "YouTube Data API v3" only. This prevents misuse if the key leaks.

**Quota:** 10,000 units/day for free. Search costs 100 units, everything else costs 1 unit. So you get ~100 searches/day or ~10,000 video/comment fetches per day.

**To increase quota:** Go to APIs & Services → YouTube Data API v3 → Quotas → Request increase. Google usually grants modest increases for free.

---

## No Registration Needed (just use these directly)

### Reddit RSS
- Just hit any Reddit URL with `.rss` appended
- No API key, no auth, no registration
- Set a browser-like User-Agent header to avoid aggressive rate limiting
- Example: `https://www.reddit.com/r/artificial/top/.rss?sort=top&t=month&limit=100`

### Hacker News Firebase API
- Base URL: `https://hacker-news.firebaseio.com/v0/`
- No API key, no auth, no rate limit
- Just make HTTP GET requests
- Example: `https://hacker-news.firebaseio.com/v0/topstories.json`

### Hacker News Algolia Search
- Base URL: `https://hn.algolia.com/api/v1/`
- No API key, no auth
- Better for keyword searches than Firebase API
- Example: `https://hn.algolia.com/api/v1/search?query=AI+agents&tags=story`

### YouTube RSS (for channel video lists)
- No API key needed — saves YouTube API quota
- Format: `https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}`
- Returns last ~15 videos with title, ID, date
- Use this to discover video IDs, then use the API only for comments/stats

### YouTube Transcripts
- Python library: `pip install youtube-transcript-api`
- No API key, no quota cost
- Extracts full video transcripts for free
- Usage: `YouTubeTranscriptApi.get_transcript(video_id)`

### News RSS Feeds
- All RSS feeds are public, no auth needed
- Just HTTP GET the feed URLs
- Parse with `feedparser` Python library: `pip install feedparser`

### ArXiv API
- Endpoint: `https://export.arxiv.org/api/query`
- No API key, no registration
- Rate limit: 1 request per 3 seconds (honor this)
- Returns Atom XML

### JobSpy
- Python library: `pip install python-jobspy`
- No API key, no registration
- Scrapes Indeed, LinkedIn, Glassdoor, Google Jobs directly
- Just import and use: `from jobspy import scrape_jobs`

---

## Python Packages to Install

```bash
# All the packages needed for data collection
pip install feedparser           # RSS feed parsing
pip install youtube-transcript-api  # YouTube transcripts (no API key)
pip install google-api-python-client  # YouTube Data API
pip install python-jobspy        # Job market scraping
pip install httpx                # Async HTTP client (for HN, ArXiv, Reddit RSS)
pip install lxml                 # XML parsing (ArXiv responses)
pip install beautifulsoup4       # HTML/XML parsing helper
```

---

## Environment Variables

```bash
# Only one API key needed!
YOUTUBE_API_KEY=your_key_from_google_cloud

# Everything else is keyless
# Reddit RSS — no key
# Hacker News — no key
# ArXiv — no key
# News RSS — no key
# JobSpy — no key
```

---

## Channel IDs for YouTube Scraping

To find a YouTube channel's ID:
1. Go to the channel page
2. Click "About" or look at the URL
3. If URL has `/channel/UCxxxx` — that's the ID
4. If URL has `/@username` — view page source and search for `channelId`
5. Or use: https://www.youtube.com/feeds/videos.xml?channel_id=PASTE_ID_HERE to verify

### Key AI/Tech Channels

| Channel | Channel ID | Focus |
|---------|-----------|-------|
| Two Minute Papers | UCbfYPyITQ-7l4upoX8nvctg | AI research papers |
| Yannic Kilcher | UCZHmQk67mSJgfCCTn7xBfew | ML paper reviews |
| AI Explained | UCNJ1Ymd5yFuUPtn21xtRbbw | AI news/explainers |
| Matt Wolfe | UCJMQEDmGRiELkGLLsZSBJjA | AI tools/news |
| Fireship | UCsBjURrPoezykLs9EqgamOA | Dev news, fast-paced |
| Sentdex | UCfzlCWGWYyIQ0aLC5w48gBQ | Python/ML tutorials |
| 3Blue1Brown | UCYO_jab_esuFRV4b17AJtAw | Math/ML explainers |
| Y Combinator | UCcefcZRL2oaA_uBNeo5UOWg | Startup advice |
| ColdFusion | UC4QZ_LsYcvcq7qOsOhpAI4A | Tech stories |
| Lenny's Podcast | UCLHNx56ekFqxKJdCLaOC3og | Product/startup |
| Boston Dynamics | UC7vVhkEfw4nOGp8TyDk7RcQ | Robotics |
| Undecided | UCRBwLPbXGsI2cJe9W1zfSjQ | Future tech |
| TheAIGRID | UCbKo3HsaBOPhdRpgFsIbtpg | AI news daily |
| Matthew Berman | UCFv89MdFnMCGuwDSJHcMbHg | AI tool reviews |
| NetworkChuck | UC9x0AN7BWHpCDHSm9NiJFJQ | Tech tutorials |

---

## Target Subreddits for Reddit RSS

| Category | Subreddits |
|----------|-----------|
| AI/ML | r/artificial, r/MachineLearning, r/LocalLLaMA, r/singularity, r/ChatGPT, r/ClaudeAI, r/StableDiffusion |
| Startups | r/startups, r/SaaS, r/Entrepreneur, r/indiehackers |
| Developer | r/programming, r/webdev, r/devops, r/ExperiencedDevs |
| Robotics | r/robotics, r/ROS |

---

## ArXiv Categories Reference

| Category | Full Name |
|----------|-----------|
| cs.AI | Artificial Intelligence |
| cs.LG | Machine Learning |
| cs.CL | Computation and Language (NLP) |
| cs.CV | Computer Vision |
| cs.RO | Robotics |
| cs.MA | Multi-Agent Systems |
| cs.SE | Software Engineering |
| cs.CR | Cryptography and Security |
| cs.DC | Distributed Computing |
| stat.ML | Machine Learning (Statistics) |
