import asyncio
import json
from datetime import date
from typing import List, Literal, Optional

from huggingface_hub import Agent
from pydantic import BaseModel, Field, HttpUrl

# ============================================================
BRIGHT_DATA_API_KEY = "YOUR_BRIGHT_DATA_KEY_HERE"
HF_API_KEY = "YOUR_HUGGING_FACE_KEY_HERE"
# ============================================================

TARGET_URL = "https://data.ca.gov/"


class Dataset(BaseModel):
    name: str
    url: Optional[str] = None
    section: Literal["popular", "recent"]
    formats: List[str] = Field(default_factory=list)
    last_updated: Optional[date] = None
    recent_views: Optional[int] = None


class DataPortalSnapshot(BaseModel):
    source_url: HttpUrl
    datasets: List[Dataset]


PROMPT = """
Step 1: Call scrape_as_markdown ONCE with this exact URL:
https://data.ca.gov/

Step 2: After the tool returns, read the tool result carefully.
The result will be Markdown text from data.ca.gov containing two sections:
"Popular Datasets" and "New and Recent Datasets". Each section has 5 cards.

Step 3: Extract data ONLY from what the tool actually returned. Do NOT use
your training knowledge. Do NOT invent dataset names. If the tool result
shows "DIR Electrician Certification Unit (ECU)", that is the name. If the
tool result shows "Updated on March 15, 2026", that is the date.

Step 4: Output ONLY a JSON object matching this shape (no fences, no commentary):

{
  "source_url": "https://data.ca.gov/",
  "datasets": [
    {
      "name": "<exact dataset name from the tool result>",
      "url": "<URL from the tool result, may be relative or absolute>",
      "section": "popular" or "recent",
      "formats": ["<format chip 1>", "<format chip 2>", ...],
      "last_updated": "<YYYY-MM-DD or null>",
      "recent_views": <integer or null>
    }
  ]
}

Do not call any tool a second time.
"""


async def main():
    bright_data_mcp_server = {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@brightdata/mcp"],
        "env": {
            "API_TOKEN": BRIGHT_DATA_API_KEY,
            "PRO_MODE": "true",
        },
    }

    agent = Agent(
        servers=[bright_data_mcp_server],
        provider="groq",
        model="meta-llama/Llama-3.3-70B-Instruct",
        api_key=HF_API_KEY,
    )

    await agent.load_tools()

    # Restrict to one tool so the model can't loop through alternatives
    agent.available_tools = [
        tool for tool in agent.available_tools
        if tool.get("function", {}).get("name") == "scrape_as_markdown"
    ]
    print(f"Tools available: {[t['function']['name'] for t in agent.available_tools]}\n")

    MAX_TOOL_CALLS = 3
    tool_call_count = 0
    final_text_chunks = []

    async for chunk in agent.run(PROMPT):
        if hasattr(chunk, "role") and chunk.role == "tool":
            tool_call_count += 1
            print(f"\n[TOOL #{tool_call_count}] {chunk.name}\n", flush=True)
            if tool_call_count >= MAX_TOOL_CALLS:
                print(f"\n*** Hit {MAX_TOOL_CALLS}-call ceiling, stopping. ***\n")
                break
        else:
            delta = chunk.choices[0].delta.content
            if delta:
                print(delta, end="", flush=True)
                final_text_chunks.append(delta)

    await agent.cleanup()

    # Parse the final text into JSON
    raw = "".join(final_text_chunks).strip()
    raw = raw.removeprefix("<|python_tag|>").strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        snapshot = DataPortalSnapshot.model_validate_json(raw)
        with open("data_ca_snapshot.json", "w", encoding="utf-8") as f:
            f.write(snapshot.model_dump_json(indent=2))
        print(f"\n\n[SUCCESS] Saved {len(snapshot.datasets)} datasets to data_ca_snapshot.json")
    except Exception as e:
        print(f"\n\n[VALIDATION FAILED] {e}")
        print(f"\nRaw output was:\n{raw[:1000]}")
        with open("raw_output.txt", "w", encoding="utf-8") as f:
            f.write(raw)
        print("\nFull raw output saved to raw_output.txt for debugging.")


if __name__ == "__main__":
    asyncio.run(main())