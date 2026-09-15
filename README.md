# Moore Foods ERP Support Assistant

A proof of concept for a RAG powered ERP Support Assistant that uses functional (but fictional) ERP documentation (`Moore_Foods_ERP_Process_Knowledge_Base_v3.docx`) to answer common process, rule, status, and role questions about an ERP system, in this case Moore Foods' fictional ERP system. As of Phase 2, it also connects to a live SQLite database to answer questions about the current status of a specific sales order or the current stock level of a specific item.

I built this to explore how AI can support everyday business practice by making organisational knowledge, and now live operational data, easier to access, without replacing the underlying systems or the people who know them.

It has also given me practical experience in Python, SQL, prompt engineering, RAG architecture, tool-calling/function-calling, and AI assisted development. AI tools helped bridge gaps in my own coding experience, giving me frameworks and troubleshooting support while I built and understood the solution myself.

## Stack

| Component | Tool |
|---|---|
| Language | Python 3.14 |
| Orchestration | LangChain (langchain, langchain-core, langchain-anthropic, langchain-chroma, langchain-voyageai) |
| Vector database | Chroma (local, file based) |
| Embedding model | Voyage AI (voyage-3) |
| LLM | Claude (claude-sonnet-4-6) via the Anthropic API, including native tool-calling |
| Document parsing | python-docx |
| Live data source | SQLite (Moore_Foods_ERP.db), accessed via Python's built-in sqlite3 module |

## Project Structure

```
Moore_Foods_ERP_RAG_Support_Assistant/
├── .env                        # API keys (not committed)
├── venv/                       # Python virtual environment (not committed)
├── Data/
│   └── Moore_Foods_ERP_Process_Knowledge_Base_v3.docx
├── Database/
│   └── Moore_Foods_ERP.db      # Phase 2, fictional live ERP database (18 tables)
├── Documentation/
│   ├── RAG_Assistant_Build_Log.docx
│   ├── Moore_Foods_RAG_Test_Script.docx
│   ├── Phase2_Scope_and_Requirements.docx
│   ├── Phase2_Function_Design.docx
│   └── Phase2_Test_Script.docx      # includes the fixes/issues log and test run summary
├── chroma_db/                   # Generated vector database (Phase 3)
├── knowledge_base.txt            # Extracted plain text (Phase 2 of docs build)
├── load_document.py              # Extracts text from .docx
├── chunk_document.py             # Splits text into heading based chunks
├── add_metadata.py               # Tags chunks with module IDs
├── build_index.py                # Embeds chunks and builds the vector database
├── test_search.py                # Checks retrieval quality
├── test_retriever.py             # Configures and tests the retriever
├── tools.py                      # Phase 2 rollout, live-data tool functions (get_order_status, get_stock_level)
├── test_tools.py                 # Phase 2 rollout, standalone tests for tools.py
└── ask.py                        # The interactive RAG assistant, now with tool-calling
```

## Glossary

A few terms used throughout this README, for anyone reading it without a RAG or AI background.

- **RAG (Retrieval Augmented Generation):** an approach where the AI looks up relevant information from a document before answering, rather than relying only on what it already knows.
- **Embedding:** a way of converting text into numbers that capture its meaning, so a computer can compare how similar two pieces of text are.
- **Vector database:** a database built to store and search embeddings quickly. Chroma is the one this project uses.
- **Chunk, chunking:** splitting a long document into smaller sections, so the assistant can retrieve just the relevant part rather than the whole document at once.
- **Retriever:** the part of the system that searches the vector database and pulls back the most relevant chunks for a given question.
- **k=4:** tells the retriever to pull back the top 4 most relevant chunks for each question, rather than just 1 or all of them.
- **System prompt:** a set of instructions given to the AI before the conversation starts, shaping how it should behave and what rules it should follow.
- **Token:** roughly a word or part of a word. AI usage and cost are both measured in tokens.
- **Tool-calling (function-calling):** a feature where the AI can request that a piece of code be run on its behalf (e.g. a database lookup), then use the result to write its final answer. This is how Phase 2's live-data lookups work.

## Setup

1. Create and activate a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
2. Install dependencies:
   ```
   pip install langchain langchain-anthropic langchain-chroma langchain-voyageai chromadb python-docx anthropic python-dotenv
   ```
3. Create a `.env` file with your API keys:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   VOYAGE_API_KEY=pa-...
   ```
4. Put your source document in `Data/`.
5. Put your SQLite database in `Database/` (Phase 2 only). `tools.py` expects it at `Database/Moore_Foods_ERP.db` by default — update the `DB_PATH` constant at the top of `tools.py` if yours lives elsewhere.

## Usage

```
python load_document.py
python build_index.py
python ask.py
```

`ask.py` runs as an interactive command line loop. Ask a question and it retrieves relevant chunks from the knowledge base and/or calls a live-data tool, then generates a grounded answer.

If you edit the source document, run `load_document.py` and `build_index.py` again to rebuild the index. Delete the `chroma_db/` folder first, otherwise new chunks get added on top of the old ones instead of replacing them.

To test the live-data functions on their own, without going through Claude at all, run:
```
python test_tools.py
```

## How It Works — Phase 1 (Documentation RAG)

**Phase 1, Planning.** I set the scope up front: the assistant answers documented process, rule, status, and role questions only, and does not access or simulate live or record level ERP data. Test questions came straight from the source document's own troubleshooting and out of scope sections, so I could grade the assistant against criteria the document itself sets.

**Phase 2, Data Preparation.** `load_document.py` pulls both paragraph and table content out of the source `.docx`, since key sections like status definitions sit in tables. `chunk_document.py` splits the text into chunks by heading number, since I wrote the source document with short, heading based sections specifically for retrieval, producing 49 chunks. `add_metadata.py` tags each chunk with a section title and a module ID using a two pass match on section number, which fixed an early bug where only the first chunk per module was getting tagged correctly.

**Phase 3, Embedding & Indexing.** `build_index.py` sends all 49 chunks to Voyage AI for embedding and stores the result in a local Chroma database.

**Phase 4, Retrieval Setup.** `test_retriever.py` sets up a retriever that returns the top 4 most relevant chunks per question, with an optional module filter for narrowing a search to a single ERP module.

**Phase 5, LLM Integration.** `ask.py` retrieves relevant chunks and sends them to Claude alongside a system prompt built from the source document's own response pattern rules. I added a conciseness rule and a tuned token limit, a truncation check using the API's `stop_reason` field, a regex based emoji filter as a backstop, and a guard against empty input.

**Phase 6, Testing & Validation.** I tested the assistant systematically against a structured test script covering 8 categories and 31 scenarios, graded against the source document's own success criteria. See Testing below.

## How It Works — Phase 2 (Live Data Retrieval)

Phase 1 was documentation-only by design; the source document's own scope explicitly deferred live/current data to a future phase. Phase 2 delivers that: a live SQLite database, two tool functions Claude can call, and a tool-calling loop wired into `ask.py`.

**Scope decision.** Rather than connecting every table in the database at once, I scoped Phase 2 ("Phase 2a") to two specific lookups: a sales order's current status, and an item's current available stock. Purchase orders, production orders, customer credit status, and any aggregate/count-style question (e.g. "how many orders are on hold") were deliberately left out of this rollout, to keep the build small, testable, and reviewable in one pass. Full reasoning is in `Documentation/Phase2_Scope_and_Requirements.docx`.

**Function design & build.** `tools.py` holds two standalone functions, `get_order_status(order_id)` and `get_stock_level(item_id)`, each returning a plain Python dict. Neither function knows anything about Claude or LangChain, they're plain SQLite lookups, which let me unit test them completely independently of the LLM before wiring anything together. `get_stock_level` in particular applies real inventory logic: available stock is calculated as on-hand quantity minus allocated quantity, filtered to `AVAILABLE` status rows only, aggregated across every warehouse an item sits in, and explicitly distinguishes "item exists but has no inventory records" from "item does not exist at all." Full function specs, including the exact SQL and the JSON schemas handed to Claude, are in `Documentation/Phase2_Function_Design.docx`.

**Standalone testing.** `test_tools.py` runs 22 checks directly against `tools.py`, no API calls involved, covering known orders, every documented order status, multi-warehouse aggregation, and edge cases like a quarantine-only item. All 22 pass.

**Tool-calling integration.** `ask.py`'s single API call became a loop: send the question (plus RAG context) to Claude along with the two tool definitions; if Claude requests a tool, run the matching Python function and send the result back; repeat until Claude gives a final answer. This is what lets one question combine a documented process explanation with a live figure in a single response.

**System prompt change.** Rule 6 (previously: decline all live-data questions) was rewritten to describe the two available tools, when to use them, and — critically, after testing surfaced gaps — exactly how to handle a tool's "not found" result and how to decline a question that's outside even the new scope. See System Prompt Rules below and the fixes/issues log at the end of `Documentation/Phase2_Test_Script.docx` for why the rule needed a second revision.

**Testing & validation.** A new structured test script (`Documentation/Phase2_Test_Script.docx`), following the same format as the Phase 1 script, covers 6 categories: order status lookups (all 8 status values), stock level lookups (single-warehouse, multi-warehouse, no-inventory, and quarantine-only items), invalid ID handling, combined documentation-plus-live-data questions, and two regression categories confirming Phase 1 behaviour and appropriately narrow-scoped declines still hold. The same document also holds the fixes/issues log and the test run summary (pass rate before and after each fix). See Testing below.

## System Prompt Rules (final state)

1. Classify the question type internally (process, rule, definition, troubleshooting, role). Never state the classification in the answer, and never use markdown, since answers are shown as plain text.
2. Answer process, rule, and definition questions only from the provided document context, no outside ERP knowledge.
3. Explain in plain language, referencing the documented process or rule.
4. Name the responsible role where relevant.
5. Never invent facts that are not in the retrieved context.
6. *(Phase 2)* You have exactly two live-data tools, `get_order_status` (a specific sales order by ID) and `get_stock_level` (a specific item's available stock by ID). Use the matching tool rather than guessing. If a tool reports an absence (order/item not found, no inventory records), state that plainly rather than speculating about alternatives it didn't report. Blend a tool result with documentation context when a question needs both. For anything outside these two lookups (aggregate counts, purchase orders, production data, customer credit, capacity, etc.), name what you *can* look up before explaining what you can't, and never offer a lookup for which no tool exists.
7. Say so honestly if the retrieved context (or a tool result) does not contain the answer.
8. Keep answers concise, 3 to 6 plain prose sentences, no headers, dividers, or emoji, leading with the direct answer first.
9. If stating how many steps or stages a process has, that number has to match what follows. Leave the number out entirely rather than risk it not matching, especially where the document describes the same process at different levels of detail in different sections.
10. Do not invent a cause for a status or a specific method by which something gets resolved. If the document does not say, say so rather than filling the gap.
11. Do not stretch a role's documented responsibility, or a tool's actual capability, to cover a different, related action unless it's explicitly stated or a tool genuinely exists for it.

## Testing

### Phase 1 (Documentation RAG)

The full test script lives in `Documentation/Moore_Foods_RAG_Test_Script.docx`, covering 8 categories: process questions, status and definition questions, role and responsibility questions, business rule questions, cross module troubleshooting, should decline (live data) questions, adversarial and edge cases including a role override attempt, and ambiguous questions, plus 6 technical checks (truncation, emoji, conciseness, empty input handling, retrieval relevance, and cost).

| Run | Date | Total | Passed | Failed | Pass Rate |
|---|---|---|---|---|---|
| Baseline (original) | 31/08/2026 | 31 | 28 | 3 | 90.3% |
| Final re-certification | 01/09/2026 | 31 | 31 | 0 | 100% |

Between the two full runs I made 36 additional retest attempts, category by category, as I applied and checked each fix. 34 of those passed and 2 failed, both on the same question, before the fix that finally resolved it.

#### Hard failures, and how I resolved them

**"What are the steps in the plan-to-produce process?"** The answer said the process has "seven stages" but then only listed 6, mixing up a 7 node overview diagram in one section with a 6 step procedure in another. I fixed this with a rule requiring any stated step count to match what is enumerated, or to be left out entirely if the model is not confident it is right.

**"What happens if a customer isn't an approved customer?"** The answer kept claiming a role's documented responsibility stretched to approving customers, an inference the source document did not support, it only ever said that role maintains records. Two prompt level fixes both failed to resolve this on retest. The real problem turned out to be a gap in my source document, not a weak prompt, it never said who approves customers. I fixed it by editing the document itself to name the approving role, separate from the record keeping role.

**"My sales order is stuck, what are all the possible reasons?"** The answer invented a cause for a credit hold that was not in the document, and ran well over my target length. The invented cause was fixed by a prompt rule. I reviewed the length overrun and decided to accept it, since this is a genuinely multi part answer and the project is a proof of concept, not a production system.

#### A structural bug I found while retesting

While rebuilding the index after editing the source document, `test_search.py` started returning duplicate results. `build_index.py` was calling Chroma's document loader against an index folder that already existed, so it was adding new chunks on top of the old ones instead of replacing them, quietly building up duplicated, stale data on every rebuild. I fixed it by deleting the index folder before every rebuild.

#### Things I noticed but decided not to chase

- Paragraph splitting on some comparison style answers, inconsistent between runs of the same question, did not affect accuracy.
- Some variation between runs on identical questions, in both retrieval and phrasing. This is normal behaviour for an LLM based system rather than a fault, but worth keeping in mind if I scale this up.
- A couple of multi branch answers running over my sentence target, accepted given how much ground those particular answers genuinely needed to cover.

### Phase 2 (Live Data Retrieval)

`tools.py` was unit tested standalone first (22/22 checks, no API involved) before any integration with Claude — see `test_tools.py`. Once wired into `ask.py`, the full Phase 2 test script (`Documentation/Phase2_Test_Script.docx`) was run twice:

| Run | Date | Total | Passed | Failed | Pass Rate |
|---|---|---|---|---|---|
| Initial run | 15/09/2026 | 23 | 20 | 3 | 87.0% |
| Re-run after Rule 6 fix | 15/09/2026 | 23 | 23 | 0 | 100% |

Full details of each failure and its fix are logged in the fixes/issues table at the end of `Documentation/Phase2_Test_Script.docx`. In short, all three initial failures traced back to the system prompt, not the tools or the database logic:

- **An item with no inventory records** got a hedged, non-committal answer instead of plainly relaying the tool's own "no records found" message.
- **A question needing an aggregate count** ("how many orders are on hold") was declined correctly, but without mentioning that specific-order and specific-item lookups are now supported.
- **A question about purchase orders** got a false capability claim, the assistant offered to look one up by ID even though no purchase order tool exists in `ask.py`.

All three were resolved with a single rewrite of Rule 6, and re-confirmed with a full 23/23 re-run, including a check that nothing in Phase 1's documentation-only behaviour had regressed.

## Cost

After a full Phase 6 test cycle, roughly 100 questions across the baseline run, the retests, and the final re certification, my actual Anthropic spend was $0.38 of a $5.00 balance, in line with my original estimate of around $0.008 per question. Voyage AI embedding spend across two full index rebuilds came to under $0.01.

Phase 2's tool-calling loop adds an extra API round trip whenever a tool is used (the model's tool request, then a follow-up call with the tool result), so live-data questions cost marginally more per question than a pure documentation lookup. I haven't separately tracked Phase 2's dollar cost yet, the volume of testing so far is small enough that it wasn't worth isolating from the Phase 1 figure above.

## Current Status

**Done:** Phases 1 through 6 (documentation RAG, planning through full testing and validation), and Phase 2 of the overall project (live data retrieval for sales order status and item stock level via tool-calling), fully tested and re-certified at 100%.

**Out of scope for this version:** purchase order and production order data, customer credit status, warehouse capacity, and any aggregate/count/list-style live-data question. These were deliberately deferred rather than built into this rollout — see `Documentation/Phase2_Scope_and_Requirements.docx` for the reasoning. A simple user-facing UI (currently command-line only) is also a separate, not-yet-started phase.

**What I want to look at next:** a Phase 2b covering purchase order and production data using the same tool-calling pattern, a simple UI (likely Streamlit) so the assistant is demoable without a terminal, and a commented, template version of the scripts so someone else could reuse them for a different project without much rework.

## Before Pushing to GitHub

Add a `.gitignore` file with at least:

```
.env
venv/
__pycache__/
chroma_db/
```

This keeps API keys, my local Python environment, and the generated vector database out of version control, where none of them belong.

`Database/Moore_Foods_ERP.db` is committed deliberately, since it's fictional test data and anyone cloning this repo needs it to run `ask.py` or `test_tools.py` out of the box. If you're adapting this project for a real database, exclude your actual data file instead and provide a way to seed a sample database, rather than committing real records.
