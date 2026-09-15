# ask.py
#
# Purpose: the actual assistant. Takes a question, retrieves relevant chunks
# from the vector database, hands both to the LLM alongside a system prompt,
# and returns a grounded answer.
#
# PHASE 2 UPDATE: this file now also gives Claude access to two live-data
# tools (get_order_status, get_stock_level) defined in tools.py, via
# Claude's tool-calling feature. Everything related to that is marked
# "PHASE 2" below so it's clear what's new versus what was already here
# from Phase 1.
#
# This file went through the most iteration of anything in the project. The
# SYSTEM_PROMPT rules below are not arbitrary, most of them exist because a
# real test failure showed a gap and the rule was added to close it. Where
# that's the case, it's noted below so you understand WHY a rule exists, not
# just what it says, which matters if you're deciding whether to keep,
# adapt, or drop a rule for your own project.

import os
import re
from dotenv import load_dotenv
from langchain_voyageai import VoyageAIEmbeddings
from langchain_chroma import Chroma
from anthropic import Anthropic

# PHASE 2: bring in the two standalone, already-tested tool functions.
# ask.py never talks to the database directly, it only calls these.
from tools import get_order_status, get_stock_level

load_dotenv()

# PROJECT SPECIFIC: this entire prompt is written for the Moore Foods ERP
# use case. Rewrite the opening paragraph and Rules 1 to 8 to describe YOUR
# assistant, its subject matter, and its tone. Rules 9, 10, and 11 (see
# notes below) are more general lessons that are worth keeping in spirit
# even for an unrelated project, since they guard against failure modes
# that aren't specific to ERP data.
SYSTEM_PROMPT = """You are the Moore Foods ERP Support Assistant. You answer questions about \
Moore Foods' fictional ERP processes, rules, statuses, and roles, using the provided document \
excerpts as your source of truth for process and policy questions, and the provided tools for \
live order and stock data.

Rules you must follow:
1. Classify the question as: process, rule, definition, troubleshooting, or role/responsibility. \
Use this classification internally to decide how to structure your answer — do not state the \
classification in your response, and do not use markdown formatting (bold, asterisks, headers, \
bullet points) since answers are displayed as plain text.
2. Answer process, rule, and definition questions only using the provided document context. Do \
not use outside knowledge about ERP systems in general.
3. Explain the answer in plain language, referencing the documented process or rule.
4. Identify the responsible role where relevant.
5. Do not infer or invent facts not present in the provided context.
6. You have exactly two live-data tools: get_order_status, which looks up a specific sales \
order by its order ID, and get_stock_level, which looks up available stock for a specific item \
by its item ID. Use the matching tool when a question asks for the current status of a specific \
order or the current stock level of a specific item, rather than answering from the document \
context or guessing. If a tool result includes a message explaining an absence (e.g. order not \
found, no inventory records for this item), state that message plainly as your answer rather \
than speculating about alternative explanations the tool didn't report or hedging with phrases \
like "if stock exists but is in a different status." If a question needs both a documented \
process explanation and a live figure (e.g. "how do I check stock, and what's the level for \
FG1001?"), use the tool for the figure and the document context for the explanation, combined \
into one answer. These two tools are the only live lookups available — you cannot look up \
purchase orders, production orders, customer credit status, warehouse capacity, or any \
aggregate, count, or list-style question, even if it sounds similar in shape to something a \
tool supports; for these, say plainly that you can look up a specific sales order's status or a \
specific item's stock level but not this, naming the specific thing you can't do rather than a \
generic "outside scope" statement, and never offer to look something up if no tool exists for it.
7. If the provided context doesn't contain the answer to a process/rule/definition question, say \
so honestly rather than guessing. If a tool reports that an order or item was not found, say so \
plainly rather than guessing at what it might be.
8. Keep answers concise: 3-6 sentences for most questions, plain prose (no headers, horizontal \
rules, or emoji). Lead with the direct answer in the first sentence, then add only the \
supporting detail (rule, role, status) that's necessary to explain it.
9. If you state how many steps, stages, or statuses a process has, that number must exactly \
match what you then list — count them before finalizing your answer. When a process is \
described at different levels of detail in different sections of the source document (e.g. a \
high-level flow diagram versus a module's detailed step list), use one consistent breakdown \
rather than blending step counts from both. If you're not confident the count is correct, omit \
the number entirely and just describe the steps.
10. Do not add plausible-sounding detail the source document doesn't actually state — this \
includes inventing a cause for a status (e.g. why a credit hold occurred) or a specific method \
by which something gets resolved (e.g. how a discrepancy gets reconciled). Describing a \
documented mechanism is fine (e.g. "the customer failed a credit check" is stated in the \
process); inventing why it happened or how it gets fixed beyond what's written is not.
11. Do not extend a role's documented responsibility to cover a different, related action unless \
the document explicitly assigns it. A role having one documented duty (e.g. "creates and \
maintains customer records") does not mean they also handle a different, unstated duty (e.g. \
approving customers) — these are not the same action even when related. If the document does \
not say who performs a specific action, say so plainly rather than inferring it from an \
adjacent responsibility that role happens to hold.
"""
# RULE NOTES, for adapting this to a different project:
#   Rule 1 exists because early testing showed the model announcing its own
#   classification ("This is a process question...") and using markdown
#   that doesn't render in a plain terminal.
#   PHASE 2: Rule 6 previously told the model to refuse live-data questions
#   as out of scope. It's been rewritten to point the model at the new
#   tools instead. This is the one rule that had to change rather than
#   just being added around, since the old and new behaviour directly
#   contradict each other.
#   PHASE 2, ROUND 2: the first rewrite of Rule 6 was too permissive about
#   what "live data" meant. Testing (Phase 2 Test Script, Categories 2 and
#   5) found three real failures: (1) the model hedged on an item with no
#   inventory records instead of stating the tool's own "not found" message
#   plainly, (2) a decline for an aggregate question ("how many orders on
#   hold") didn't mention that specific-order/item lookups ARE supported,
#   and (3) the model falsely offered to look up a purchase order by ID
#   even though no PO tool exists, i.e. it pattern-matched the SHAPE of a
#   supported lookup onto a table it has no tool for. Rule 6 was rewritten
#   again to name the two tools explicitly, tell the model to trust a
#   tool's own absence message rather than speculate further, and give it
#   a specific decline template (name what IS supported, then name the
#   specific thing that isn't) instead of a generic "outside scope" line.
#   If you adapt this project and add more tools later, revisit this rule
#   again, the same failure mode (assuming a new-shaped question maps to
#   an existing tool) will likely resurface with each new tool you add.
#   Rule 8 plus the max_tokens setting below (see HARDENING) exist together,
#   without an explicit length target, answers ran long and hard to scan.
#   Rule 9 exists because a real test failure had the model state a process
#   has "seven stages" then list six, caused by the source document
#   describing the same process at two different levels of detail. If your
#   own document has that same pattern (an overview diagram plus a detailed
#   procedure elsewhere), keep this rule.
#   Rules 10 and 11 exist because prompt instructions ALONE weren't enough
#   to stop the model inventing plausible-sounding detail, e.g. assuming a
#   role's responsibility extended further than the document actually said.
#   Worth knowing: in this project, rules 10/11 reduced but didn't fully
#   eliminate this failure mode on their own, the actual fix that finally
#   worked was editing the SOURCE DOCUMENT to state the missing fact
#   explicitly, removing the gap the model kept trying to fill. If you hit a
#   similar repeated invention problem, don't assume a better prompt will
#   always fix it, check whether your source document actually contains the
#   fact you're expecting the model to know.

# PHASE 2: tool schemas, taken directly from the Phase 2 Function Design
# document. This is what tells Claude these tools exist, what they're for,
# and what argument each one needs.
TOOLS = [
    {
        "name": "get_order_status",
        "description": (
            "Look up the current status, customer, and line items for a sales "
            "order by its order ID. Use this when the user asks about the "
            "status, contents, or hold reason for a specific order."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The sales order ID, e.g. 'SO10002'",
                }
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "get_stock_level",
        "description": (
            "Look up available stock for an item by its item ID, broken down "
            "by warehouse. Use this when the user asks about current stock, "
            "inventory, or availability for a specific item."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {
                    "type": "string",
                    "description": "The item ID, e.g. 'FG1001'",
                }
            },
            "required": ["item_id"],
        },
    },
]

# PHASE 2: maps a tool name (as Claude will send it) to the actual Python
# function that carries it out. This is what lets the loop below call the
# right function without a long if/elif chain.
TOOL_FUNCTIONS = {
    "get_order_status": get_order_status,
    "get_stock_level": get_stock_level,
}


def strip_emoji(text):
    # HARDENING, optional: the prompt rules above already tell the model not
    # to use emoji, but a prompt instruction is guidance, not a guarantee.
    # This is a code-level backstop that strips any emoji regardless of
    # whether the model follows the instruction. Safe to remove if emoji in
    # answers isn't a concern for your use case.
    emoji_pattern = re.compile(
        "[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U00002600-\U000026FF]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text).strip()

# Must match the embedding model used in build_index.py (see that file's
# comments). k=4 must also match (or be a deliberate, considered choice
# different from) test_retriever.py's setting.
embeddings = VoyageAIEmbeddings(model="voyage-3")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 4})

client = Anthropic()

def ask(question):
    retrieved_docs = retriever.invoke(question)
    context = "\n\n---\n\n".join(doc.page_content for doc in retrieved_docs)

    # PROJECT SPECIFIC: "Moore Foods ERP knowledge base" here is just label
    # text shown to the LLM, update it to describe your own knowledge base.
    user_message = f"""Context from the Moore Foods ERP knowledge base:

{context}

---

Question: {question}"""

    # PHASE 2: messages is now a list we can append to, rather than a single
    # inline message, because a tool-calling exchange takes multiple turns:
    # our question, Claude's tool request, our tool result, Claude's final
    # answer. Everything from here to the return statement replaces the
    # single client.messages.create(...) call from Phase 1.
    messages = [{"role": "user", "content": user_message}]
    tools_used = []  # PHASE 2: tracked just so we can report it below

    while True:
        response = client.messages.create(
            # PROJECT SPECIFIC: pick whichever current Claude model fits your
            # cost/quality needs. Check Anthropic's current model list rather
            # than assuming this exact model name is still current when you
            # read this.
            model="claude-sonnet-4-6",
            # HARDENING / WHY THIS VALUE: this started at 800 (a fairly generous
            # ceiling), then was tuned down to 400 once Rule 8's conciseness
            # target was added, so the hard cutoff roughly matches the target
            # length rather than sitting far above it. If you loosen or remove
            # Rule 8's sentence-count target, you'll likely need to raise this
            # back up too, otherwise answers can get cut off mid-sentence on
            # genuinely complex, multi-part questions.
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=TOOLS,  # PHASE 2
        )

        if response.stop_reason != "tool_use":
            # Claude has given its final answer — no more tool calls pending.
            final_text = "".join(
                block.text for block in response.content if block.type == "text"
            )
            return strip_emoji(final_text), retrieved_docs, response.stop_reason, tools_used

        # PHASE 2: Claude wants to call one or more tools. Its response is
        # added to the conversation first (required by the API), then we
        # run each requested tool and send the results back as a new
        # "user" turn containing tool_result blocks.
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            func = TOOL_FUNCTIONS.get(block.name)
            if func is None:
                result = {"error": True, "message": f"Unknown tool: {block.name}"}
            else:
                result = func(**block.input)
            tools_used.append((block.name, block.input))
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result),
                }
            )

        messages.append({"role": "user", "content": tool_results})
        # Loop back around: Claude now sees the tool result(s) and either
        # asks for another tool or gives its final answer.

if __name__ == "__main__":
    while True:
        q = input("\nAsk a question (or 'quit'): ")
        if q.lower() == "quit":
            break
        # HARDENING: guards against pressing Enter with nothing typed, which
        # otherwise sends an empty string to the embedding API and crashes
        # with an unhelpful error several layers down the stack.
        if not q.strip():
            continue
        answer, sources, stop_reason, tools_used = ask(q)
        print(f"\nAnswer:\n{answer}")
        # HARDENING: surfaces truncation instead of letting a cut-off answer
        # pass silently as if it were complete.
        if stop_reason == "max_tokens":
            print("\nWarning: this answer was cut off because it hit the token limit. Consider raising max_tokens.")
        print(f"\n(Based on {len(sources)} retrieved sections" + (f", {len(tools_used)} live data lookup(s): {tools_used})" if tools_used else ")"))
