"""Agent 9: Product Discoverer — Auto-discovers new products from community posts."""

from agno.agent import Agent
from agno.models.azure import AzureOpenAI

from agents.tools.sql_tool import SQLReadTool
from agents.tools.calculate_tool import CalculateTool
from agents.config import (
    DATABASE_URL, AGENT_TABLE_PERMISSIONS, AGENT_MODELS,
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION,
    get_deployment_for_model,
)

INSTRUCTIONS = """\
You discover NEW products, tools, and frameworks being discussed in the community
that are NOT yet in the discovered_products table.

WORKFLOW:

STEP 1: Get known products
SELECT canonical_name, aliases FROM discovered_products

STEP 2: Scan recent posts for entity-like mentions not in the known list
Look at recent high-engagement posts:
SELECT id, body, COALESCE((raw_metadata->>'score')::int, 0) as score,
       posted_at, platform_id
FROM posts
WHERE posted_at > NOW() - INTERVAL '7 days'
AND LENGTH(body) > 100
ORDER BY COALESCE((raw_metadata->>'score')::int, 0) DESC LIMIT 50

STEP 3: For each candidate product you identify in the post text:
Check if it appears in multiple posts by different users:
SELECT COUNT(DISTINCT user_id) as unique_users, COUNT(*) as total_mentions
FROM posts
WHERE LOWER(body) LIKE LOWER('%{candidate}%')
AND posted_at > NOW() - INTERVAL '30 days'

STEP 4: Check if it's discussed in recommendation/complaint context
SELECT p.body FROM posts p
WHERE LOWER(p.body) LIKE LOWER('%{candidate}%')
AND (LOWER(p.body) LIKE '%recommend%' OR LOWER(p.body) LIKE '%switched to%'
     OR LOWER(p.body) LIKE '%replaced%' OR LOWER(p.body) LIKE '%better than%'
     OR LOWER(p.body) LIKE '%worst%' OR LOWER(p.body) LIKE '%broken%')
LIMIT 5

STEP 5: For each validated candidate, classify:
- name: canonical product name
- category: ai_framework / dev_tool / saas / library / model / platform
- aliases: alternative names or abbreviations
- confidence: 0.0 to 1.0

OUTPUT: JSON array of new products to add:
{
  "new_products": [
    {
      "canonical_name": "Cursor",
      "category": "dev_tool",
      "aliases": ["cursor.sh", "cursor ai"],
      "confidence": 0.95,
      "evidence": {
        "unique_users_mentioning": 23,
        "total_mentions_30d": 67,
        "context_types": ["recommendation", "comparison"],
        "sample_quotes": ["Just switched from Copilot to Cursor...", "Cursor is amazing for..."]
      },
      "reasoning": "Mentioned by 23 unique users in recommendation context. Multiple comparison posts vs Copilot."
    }
  ]
}

Only include products with confidence >= 0.6.
Exclude generic terms, programming languages, and well-known companies (Google, Microsoft, etc.)."""


def create_product_discoverer_agent() -> Agent:
    model_name = AGENT_MODELS["product_discoverer"]
    sql_tool = SQLReadTool(
        db_url=DATABASE_URL,
        allowed_tables=AGENT_TABLE_PERMISSIONS["product_discoverer"],
    )
    calc_tool = CalculateTool()

    return Agent(
        name="Product Discoverer",
        model=AzureOpenAI(
            id=get_deployment_for_model(model_name),
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
        ),
        tools=[sql_tool, calc_tool],
        instructions=INSTRUCTIONS,
        markdown=False,
    )
