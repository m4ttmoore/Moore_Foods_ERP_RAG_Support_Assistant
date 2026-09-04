# Moore Foods ERP Support Assistant

A proof of concept for a RAG powered ERP Support Assistant that uses functional (but fictional) ERP documentation (`Moore_Foods_ERP_Process_Knowledge_Base_v3.docx`) to answer common process, rule, status, and role questions about an ERP system, in this case Moore Foods' fictional ERP system.

I built this to explore how AI can support everyday business practice by making organisational knowledge easier to access, without replacing the underlying systems or the people who know them.

It has also given me practical experience in Python, SQL, prompt engineering, RAG architecture and AI assisted development. AI tools helped bridge gaps in my own coding experience, giving me frameworks and troubleshooting support while I built and understood the solution myself. A separate SQL database gives me a foundation to build on for a future phase.

## Stack

| Component | Tool |
|---|---|
| Language | Python 3.14 |
| Orchestration | LangChain (langchain, langchain-core, langchain-anthropic, langchain-chroma, langchain-voyageai) |
| Vector database | Chroma (local, file based) |
| Embedding model | Voyage AI (voyage-3) |
| LLM | Claude (claude-sonnet-4-6) via the Anthropic API |
| Document parsing | python-docx |

## Project Structure

```
Moore_Foods_ERP_RAG_Support_Assistant/
├── .env                       # API keys (not committed)
├── venv/                      # Python virtual environment (not committed)
├── Data/
│   └── Moore_Foods_ERP_Process_Knowledge_Base_v3.docx
├── Documentation/
│   ├── RAG_Assistant_Build_Log.docx
│   └── Moore_Foods_RAG_Test_Script.docx
├── chroma_db/                  # Generated vector database (Phase 3)
├── knowledge_base.txt           # Extracted plain text (Phase 2)
├── load_document.py             # Phase 2, extracts text from .docx
├── chunk_document.py            # Phase 2, splits text into heading based chunks
├── add_metadata.py              # Phase 2, tags chunks with module IDs
├── build_index.py               # Phase 3, embeds chunks and builds the vector database
├── test_search.py               # Phase 3, checks retrieval quality
├── test_retriever.py            # Phase 4, configures and tests the retriever
└── ask.py                       # Phase 5, the interactive RAG assistant
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

## Setup

1. Create and activate a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
2. Install dependencies:
   ```
   pip install langchain langchain-anthropic langchain-chroma langchain-voyageai chromadb python-docx
   ```
3. Create a `.env` file with your API keys:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   VOYAGE_API_KEY=pa-...
   ```
4. Put your source document in `Data/`.

## Usage

```
python load_document.py
python build_index.py
python ask.py
```

`ask.py` runs as an interactive command line loop. Ask a question and it retrieves relevant chunks from the knowledge base and generates a grounded answer.

If you edit the source document, run `load_document.py` and `build_index.py` again to rebuild the index. Delete the `chroma_db/` folder first, otherwise new chunks get added on top of the old ones instead of replacing them.

## How It Works

**Phase 1, Planning.** I set the scope up front: the assistant answers documented process, rule, status, and role questions only, and does not access or simulate live or record level ERP data. Test questions came straight from the source document's own troubleshooting and out of scope sections, so I could grade the assistant against criteria the document itself sets.

**Phase 2, Data Preparation.** `load_document.py` pulls both paragraph and table content out of the source `.docx`, since key sections like status definitions sit in tables. `chunk_document.py` splits the text into chunks by heading number, since I wrote the source document with short, heading based sections specifically for retrieval, producing 49 chunks. `add_metadata.py` tags each chunk with a section title and a module ID using a two pass match on section number, which fixed an early bug where only the first chunk per module was getting tagged correctly.

**Phase 3, Embedding & Indexing.** `build_index.py` sends all 49 chunks to Voyage AI for embedding and stores the result in a local Chroma database.

**Phase 4, Retrieval Setup.** `test_retriever.py` sets up a retriever that returns the top 4 most relevant chunks per question, with an optional module filter for narrowing a search to a single ERP module.

**Phase 5, LLM Integration.** `ask.py` retrieves relevant chunks and sends them to Claude alongside a system prompt built from the source document's own response pattern rules. I added a conciseness rule and a tuned token limit, a truncation check using the API's `stop_reason` field, a regex based emoji filter as a backstop, and a guard against empty input.

**Phase 6, Testing & Validation.** I tested the assistant systematically against a structured test script covering 8 categories and 31 scenarios, graded against the source document's own success criteria. See Testing below.

## System Prompt Rules (final state)

1. Classify the question type internally (process, rule, definition, troubleshooting, role). Never state the classification in the answer, and never use markdown, since answers are shown as plain text.
2. Answer only from the provided document context, no outside ERP knowledge.
3. Explain in plain language, referencing the documented process or rule.
4. Name the responsible role where relevant.
5. Never invent facts that are not in the retrieved context.
6. Decline questions that need live or current data, rather than guessing.
7. Say so honestly if the retrieved context does not contain the answer.
8. Keep answers concise, 3 to 6 plain prose sentences, no headers, dividers, or emoji, leading with the direct answer first.
9. If stating how many steps or stages a process has, that number has to match what follows. Leave the number out entirely rather than risk it not matching, especially where the document describes the same process at different levels of detail in different sections.
10. Do not invent a cause for a status or a specific method by which something gets resolved. If the document does not say, say so rather than filling the gap.
11. Do not stretch a role's documented responsibility to cover a different, related action unless the document explicitly assigns it.

## Testing

The full test script lives in `Documentation/Moore_Foods_RAG_Test_Script.docx`, covering 8 categories: process questions, status and definition questions, role and responsibility questions, business rule questions, cross module troubleshooting, should decline (live data) questions, adversarial and edge cases including a role override attempt, and ambiguous questions, plus 6 technical checks (truncation, emoji, conciseness, empty input handling, retrieval relevance, and cost).

| Run | Date | Total | Passed | Failed | Pass Rate |
|---|---|---|---|---|---|
| Baseline (original) | 31/08/2026 | 31 | 28 | 3 | 90.3% |
| Final re-certification | 01/09/2026 | 31 | 31 | 0 | 100% |

Between the two full runs I made 36 additional retest attempts, category by category, as I applied and checked each fix. 34 of those passed and 2 failed, both on the same question, before the fix that finally resolved it.

### Hard failures, and how I resolved them

**"What are the steps in the plan-to-produce process?"** The answer said the process has "seven stages" but then only listed 6, mixing up a 7 node overview diagram in one section with a 6 step procedure in another. I fixed this with a rule requiring any stated step count to match what is enumerated, or to be left out entirely if the model is not confident it is right.

**"What happens if a customer isn't an approved customer?"** The answer kept claiming a role's documented responsibility stretched to approving customers, an inference the source document did not support, it only ever said that role maintains records. Two prompt level fixes both failed to resolve this on retest. The real problem turned out to be a gap in my source document, not a weak prompt, it never said who approves customers. I fixed it by editing the document itself to name the approving role, separate from the record keeping role.

**"My sales order is stuck, what are all the possible reasons?"** The answer invented a cause for a credit hold that was not in the document, and ran well over my target length. The invented cause was fixed by a prompt rule. I reviewed the length overrun and decided to accept it, since this is a genuinely multi part answer and the project is a proof of concept, not a production system.

### A structural bug I found while retesting

While rebuilding the index after editing the source document, `test_search.py` started returning duplicate results. `build_index.py` was calling Chroma's document loader against an index folder that already existed, so it was adding new chunks on top of the old ones instead of replacing them, quietly building up duplicated, stale data on every rebuild. I fixed it by deleting the index folder before every rebuild.

### Things I noticed but decided not to chase

- Paragraph splitting on some comparison style answers, inconsistent between runs of the same question, did not affect accuracy.
- Some variation between runs on identical questions, in both retrieval and phrasing. This is normal behaviour for an LLM based system rather than a fault, but worth keeping in mind if I scale this up.
- A couple of multi branch answers running over my sentence target, accepted given how much ground those particular answers genuinely needed to cover.

## Cost

After a full Phase 6 test cycle, roughly 100 questions across the baseline run, the retests, and the final re certification, my actual Anthropic spend was $0.38 of a $5.00 balance, in line with my original estimate of around $0.008 per question. Voyage AI embedding spend across two full index rebuilds came to under $0.01.

## Current Status

**Done:** Phases 1 through 6, planning, data preparation, embedding and indexing, retrieval setup, LLM integration with hardening, and full testing and validation.

**Out of scope for this version:** any live SQL database connectivity. My source document sets this out as a separate future phase, not part of the current build.

**What I want to look at next:** how to make the assistant more scalable, beyond a single local Chroma instance and one document, and building a commented, template version of the scripts so someone else could reuse them for a different project without much rework.

## Before Pushing to GitHub

Add a `.gitignore` file with at least:

```
.env
venv/
__pycache__/
chroma_db/
```

This keeps API keys, my local Python environment, and the generated vector database out of version control, where none of them belong.
