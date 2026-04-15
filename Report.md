# AI Web Scraper for the California Open Data Portal

**Repository:** https://github.com/akalin23/ca-data-scraper
**Dataset:** https://github.com/akalin23/ca-data-scraper/blob/main/data_ca_snapshot.json
**Source code:** https://github.com/akalin23/ca-data-scraper/blob/main/agent.py

## 1. Target site

I chose the California Open Data Portal homepage at https://data.ca.gov/.
The page exposes two sections — "Popular Datasets" and "New and Recent
Datasets" — each containing five cards with dataset names, URLs, file
format chips, update dates, and view counts. The two sections expose
slightly different fields per card (popular cards show view counts; recent
cards show update dates), which makes the extraction task non-trivial
enough to be a real test of the AI scraper pattern.

I chose this target over alternatives like Kaggle or sports sites because
data.ca.gov serves clean HTML to scrapers without bot-protection
challenges. This let the project focus on the AI extraction pipeline
itself rather than on fighting anti-bot measures.

## 2. Scraper architecture

I followed the pattern from the Bright Data + Hugging Face article series.
The pipeline runs in three stages:

1. **Fetch as Markdown.** Bright Data's `scrape_as_markdown` MCP tool is
   launched as a subprocess via `npx -y @brightdata/mcp`. It fetches the
   target URL and converts the raw HTML to clean Markdown, stripping
   navigation chrome and keeping only content.

2. **Extract with an LLM and a Pydantic schema.** A Pydantic model
   (`DataPortalSnapshot` containing a list of `Dataset` objects) describes
   the desired output structure, including a `Literal["popular", "recent"]`
   type to discriminate between the two sections of the page. Almost every
   field is Optional, following the article's guidance that nullable
   fields prevent the LLM from hallucinating values for fields that aren't
   present. The schema is described in the prompt and the LLM is asked to
   return JSON conforming to it.

3. **Validate.** The script calls `model_validate_json` on the LLM's
   output. Validation failures are caught and the raw output is dumped to
   `raw_output.txt` for debugging.

The implementation uses `huggingface_hub.Agent` with `provider="groq"` and
the `meta-llama/Llama-3.3-70B-Instruct` model. After `load_tools()` the
agent's tool list is filtered down to just `scrape_as_markdown`, so the
model cannot loop through alternative tools — a precaution learned from
early experimentation where the agent ran 600+ tool calls in a single
session. A `MAX_TOOL_CALLS = 3` counter in the streaming loop provides a
hard ceiling against runaway tool-call loops. The prompt includes explicit
"do not invent" anti-hallucination instructions and is structured as four
numbered steps to keep the model on track.

## 3. Performance assessment

The scraper validated against the Pydantic schema, but **comparison of the
output to the live data.ca.gov page revealed a critical hallucination
problem that schema validation alone could not detect.** This is the
central finding of the project.

I tested two models served via Groq through Hugging Face routing:

- **Qwen3-32B**: produced agency names rather than dataset names
  ("California Department of Transportation (DOT)", "Department of Finance
  (DOF)"). None of these are real dataset entries on the page — they are
  California government nouns the model produced from its training data.
  URLs followed an invented `/data/directory/...` pattern rather than the
  real `/dataset/...` pattern.

- **Llama-3.3-70B-Instruct**: correctly identified some popular-section
  entries — "DIR Electrician Certification Unit (ECU)" matches the live
  page — but invented placeholder names for the recent section ("New
  Dataset 1" through "New Dataset 5", with view counts of 5, 2, 1).

A third run with a stricter prompt produced a useful diagnostic: the model
explicitly stated "the result of the function call is not provided here,"
suggesting that the failure originates in the round-trip between the MCP
tool result and the LLM's input — possibly a token-budget or
provider-formatting issue — rather than in the model's reasoning.

This experience drove the assessment framework I would recommend for any
AI scraper:

- **Extraction accuracy against ground truth**, not just schema validity.
  This is the only check that catches hallucination. For data.ca.gov, a
  free ground-truth source exists at
  `https://data.ca.gov/api/3/action/package_search`, which would enable
  mechanical field-by-field grading.
- **Schema validation rate** across many runs, to catch LLM drift.
- **Fetch success rate** measured independently of LLM behavior, to
  isolate Bright Data issues from extraction issues.
- **Cost and latency per page**, including the LLM tokens spent reading
  the page Markdown.

A traditional CSS-selector scraper cannot fail in the same way an AI
scraper can — it returns real DOM content or nothing. The AI scraper
pattern earns its keep when one schema needs to span many sites; for a
single stable target like data.ca.gov, the AI approach is structurally
more expensive and more failure-prone than rule-based extraction.

## 4. Output

`data_ca_snapshot.json` contains 10 dataset records produced by the
Llama-3.3-70B-Instruct run. Per the assessment above, the popular-section
entries are partially verified against the live page; the recent-section
entries are known-fabricated and are documented as such here. The dataset
is included in the repository for transparency about both the working and
the failure modes of the pipeline, and so that any reader can reproduce
the assessment by comparing the JSON against the live page.

## 5. Conclusion

The AI scraper pattern is structurally sound: fetch, extract via an LLM
constrained by a Pydantic schema, validate. The implementation friction I
encountered — provider routing, model availability churn, model behavior
on tool calls, and ultimately the tool-result round-tripping issue that
caused the hallucination — is a real cost that's invisible until ground
truth is checked.

For this single-page target, a traditional CSS-selector scraper would be
faster, cheaper, and more reliable. The AI pattern's value proposition is
"one schema, many sources," which couldn't be tested in this single-site
project. But the failure modes documented in section 3 would all need to
be addressed before the pattern could be scaled to many targets in
production.
