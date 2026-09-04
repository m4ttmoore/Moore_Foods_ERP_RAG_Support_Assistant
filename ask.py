# ask.py
#
# Purpose: the actual assistant. Takes a question, retrieves relevant chunks
# from the vector database, hands both to the LLM alongside a system prompt,
# and returns a grounded answer.
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

load_dotenv()

# PROJECT SPECIFIC: this entire prompt is written for the Moore Foods ERP
# use case. Rewrite the opening paragraph and Rules 1 to 8 to describe YOUR
# assistant, its subject matter, and its tone. Rules 9, 10, and 11 (see
# notes below) are more general lessons that are worth keeping in spirit
# even for an unrelated project, since they guard against failure modes
# that aren't specific to ERP data.
SYSTEM_PROMPT = """You are the Moore Foods ERP Support Assistant. You answer questions about \
Moore Foods' fictional ERP processes, rules, statuses, and roles, using ONLY the provided \
document excerpts as your source of truth.

Rules you must follow:
1. Classify the question as: process, rule, definition, troubleshooting, or role/responsibility. \
Use this classification internally to decide how to structure your answer — do not state the \
classification in your response, and do not use markdown formatting (bold, asterisks, headers, \
bullet points) since answers are displayed as plain text.
2. Answer only using the provided context. Do not use outside knowledge about ERP systems in general.
3. Explain the answer in plain language, referencing the documented process or rule.
4. Identify the responsible role where relevant.
5. Do not infer or invent facts not present in the provided context.
6. If the question requires current, live, or record-level data (e.g. "how many orders are open \
right now", "what is customer X's current status"), say plainly that this is outside your \
current documentation-only scope, and that live-data retrieval is a planned future capability. \
Do not guess.
7. If the provided context doesn't contain the answer, say so honestly rather than guessing.
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
        messages=[{"role": "user", "content": user_message}],
    )
    # response.stop_reason tells you WHY the model stopped generating.
    # "end_turn" means it finished naturally; "max_tokens" means it got cut
    # off by the limit above. Returning this lets the caller warn on
    # truncation rather than silently showing a cut-off answer.
    return strip_emoji(response.content[0].text), retrieved_docs, response.stop_reason

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
        answer, sources, stop_reason = ask(q)
        print(f"\nAnswer:\n{answer}")
        # HARDENING: surfaces truncation instead of letting a cut-off answer
        # pass silently as if it were complete.
        if stop_reason == "max_tokens":
            print("\nWarning: this answer was cut off because it hit the token limit. Consider raising max_tokens.")
        print(f"\n(Based on {len(sources)} retrieved sections)")
