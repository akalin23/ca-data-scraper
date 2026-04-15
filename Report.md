# AI Web Scraper for California Open Data Portal

**Repo:** https://github.com/akalin23/ca-data-scraper
**Dataset:** https://github.com/akalin23/ca-data-scraper/blob/main/data_ca_snapshot.json

## 1. Target
California Open Data Portal homepage (https://data.ca.gov/). Two sections —
"Popular Datasets" and "New and Recent Datasets" — each with five cards
containing names, URLs, formats, dates, and view counts. Chosen because the
site serves clean HTML to scrapers, allowing the focus to stay on the AI
extraction step rather than on bot-evasion.

## 2. Scraper
Followed the pattern from the Bright Data + Hugging Face article series:
Bright Data's `scrape_as_markdown` MCP tool fetches the page; an LLM reads
the Markdown and fills a Pydantic schema; the script validates and writes
JSON. Implemented with `huggingface_hub.Agent` routing to Groq, using
Llama-3.3-70B-Versatile.

## 3. Performance assessment
Initial validation against the Pydantic schema passed, but **comparison of
the output to the live page revealed a critical hallucination problem**.

I tested two models:
- **Qwen3-32B**: produced agency names instead of dataset names ("California
  Department of Transportation", "Department of Finance"). None matched
  real entries on the page.
- **Llama-3.3-70B-Versatile**: correctly identified some popular-section
  entries (DIR Electrician Certification Unit was verified against the live
  page), but invented placeholder names for the recent section ("New Dataset
  1" through "New Dataset 5" with view counts of 5, 2, 1).

A third run with a stricter prompt produced a useful diagnostic: the model
explicitly stated that the tool result was not available to it, suggesting
the failure originates in the round-trip between the MCP tool result and the
LLM's input rather than in the model's behavior.

This is the central finding of the project: **schema validity is necessary
but not sufficient for assessing AI-scraper output**. A scraper can pass
validation and still produce fabricated data. Traditional CSS-selector
scrapers cannot fail this way — they return real DOM content or nothing.

A full assessment framework for an AI scraper should track:
- **Extraction accuracy** against ground-truth (here, the live page)
- **Schema validation rate**
- **Fetch success rate** (independent of LLM behavior)
- **Cost and latency per page**

For data.ca.gov specifically, a free ground-truth source exists at
`https://data.ca.gov/api/3/action/package_search`, which would enable
mechanical field-by-field grading in future iterations.

## 4. Output
`data_ca_snapshot.json` contains 10 dataset records. Per the assessment
above, the popular-section entries are partially verified against the live
page; the recent-section entries are known-fabricated and labeled as such
in this report.

## 5. Conclusion
The AI-scraper pattern is structurally sound — fetch, extract, validate.
The implementation friction I encountered (provider routing, model behavior,
tool-result round-tripping) is real and not always visible until ground
truth is checked. For a stable single-page target like data.ca.gov, a
traditional scraper would be more reliable and cheaper. The AI pattern's
genuine value is when one schema needs to span many sites — the value
proposition couldn't be tested in this single-site project, but the failure
modes I documented would all need to be solved before scaling.
