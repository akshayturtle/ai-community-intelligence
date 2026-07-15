# Contributing

Thanks for your interest in contributing to AI Community Intelligence.

## Getting started
1. Fork and clone the repo.
2. Create a virtualenv and `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and fill in the required keys.
4. Run the test suite before opening a PR.

## Adding a new scraper
- Put the scraper under `scrapers/` and register it in `PROCESSOR_ORDER`.
- Reuse `scrapers/proxy.py` for any source that needs a residential proxy.
- Wrap rate-limited calls in `with_backoff()` from `scrapers/backoff.py`.

## Pull requests
- Keep PRs focused and small where possible.
- Describe what changed and why in the PR body.
- Link any related issue.
