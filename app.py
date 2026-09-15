# app.py
#
# Phase 3, Step 3: adds error handling per the Phase 3 Function & Layout
# Design document, Section 6 — a startup guard around the ask.py import
# (covers a missing/unavailable database or vector index), a try/except
# around each ask() call (covers an API failure mid-conversation), and
# the empty/whitespace input guard already present in the command-line
# version, reproduced here for the chat_input widget.

import streamlit as st

st.title("Moore Foods ERP Support Assistant")
st.caption(
    "Ask about Moore Foods' documented ERP processes and rules, or look up "
    "the live status of a specific sales order or the stock level of a "
    "specific item. See \"What can I ask?\" below for examples and current "
    "limitations."
)

with st.expander("What can I ask?"):
    st.markdown(
        """
**Documented processes and rules** — e.g. "How do I process a sales order
from start to finish?" or "What does CR-HOLD mean?"

**A specific sales order's status** — try `SO10001` through `SO10013`
(e.g. "What's the status of order SO10002?")

**A specific item's available stock** — try `FG1001`, `FG2001`, or `FG1003`
(e.g. "What's the available stock for FG1001?")

**Not yet supported:** purchase orders, production orders, customer credit
status, warehouse capacity, or aggregate/count questions (e.g. "how many
orders are on hold"). The assistant will tell you plainly if you ask one
of these, rather than guessing.

**Source data:** every answer is grounded in the actual process
documentation and database below, viewable on GitHub —
[process documentation](https://github.com/m4ttmoore/Moore_Foods_ERP_RAG_Support_Assistant/blob/main/Data/Moore_Foods_ERP_Process_Knowledge_Base_v3.docx)
and [database file](https://github.com/m4ttmoore/Moore_Foods_ERP_RAG_Support_Assistant/blob/main/Database/Moore_Foods_ERP.db).
        """
    )

# STARTUP GUARD: ask.py builds the embeddings client, Chroma connection,
# and Anthropic client at import time (see ask.py's module-level code).
# If the vector index or database is missing, or an API key is absent,
# that happens here, before the chat UI ever renders. Catching it lets
# us show a clear message instead of Streamlit's default traceback page.
try:
    from ask import ask
except Exception as e:
    st.error(
        "The assistant couldn't start up. This usually means the vector "
        "index, database, or API keys aren't set up correctly. "
        f"Details: {e}"
    )
    st.stop()

# Session state holds the conversation so far. Streamlit re-runs this
# whole script on every interaction, so without this, the chat history
# would disappear after every message. Each entry now carries the extra
# detail (sources, tools_used, stop_reason) needed for the expander,
# per the design doc's session state table.
if "messages" not in st.session_state:
    st.session_state.messages = []


def render_detail(sources, tools_used, stop_reason):
    # Mirrors the command-line version's closing line:
    # "(Based on N retrieved sections, M live data lookup(s): [...])"
    # in an expander instead of plain text, per design doc Section 4.
    with st.expander("Details"):
        st.write(f"Based on {len(sources)} retrieved section(s).")
        if tools_used:
            st.write(f"Live data lookup(s) used: {len(tools_used)}")
            for name, inputs in tools_used:
                st.write(f"- {name}({inputs})")
        if stop_reason == "max_tokens":
            st.warning(
                "This answer was cut off because it hit the token limit."
            )


# Redraw every message from this session, oldest to newest. User
# messages have no detail to show; assistant messages do.
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])
        if message["role"] == "assistant":
            render_detail(
                message["sources"], message["tools_used"], message["stop_reason"]
            )

# Example question buttons: give a first-time visitor (e.g. from LinkedIn,
# with no context on scope) a one-click way to see the assistant actually
# work, using real questions and real IDs rather than requiring them to
# guess what's answerable.
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

st.write("Try an example:")
example_cols = st.columns(3)
if example_cols[0].button("How do I process a sales order from start to finish?"):
    st.session_state.pending_question = (
        "How do I process a sales order from start to finish?"
    )
if example_cols[1].button("What's the status of order SO10002?"):
    st.session_state.pending_question = "What's the status of order SO10002?"
if example_cols[2].button("What's the available stock for FG1001?"):
    st.session_state.pending_question = "What's the available stock for FG1001?"

# The chat input box, pinned to the bottom of the page by Streamlit.
user_question = st.chat_input("Ask a question")

# A button click sets pending_question and triggers a rerun; pick that up
# here as if it had been typed, then clear it so it doesn't repeat.
if st.session_state.pending_question:
    user_question = st.session_state.pending_question
    st.session_state.pending_question = None

# EMPTY INPUT GUARD: matches ask.py's own "if not q.strip(): continue"
# check in its command-line loop. st.chat_input already won't submit a
# purely empty box, but this guards against whitespace-only input too.
if user_question and user_question.strip():
    # Show the user's own message immediately.
    with st.chat_message("user"):
        st.write(user_question)
    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_question,
            "sources": None,
            "tools_used": None,
            "stop_reason": None,
        }
    )

    # MID-CONVERSATION ERROR GUARD: an API error, a dropped connection,
    # or an unexpected exception inside ask() shouldn't crash the whole
    # page. Catch it, show a clear message, and don't add a broken
    # assistant entry to session state.
    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking..."):
                answer, sources, stop_reason, tools_used = ask(user_question)
            st.write(answer)
            render_detail(sources, tools_used, stop_reason)
        except Exception as e:
            st.error(
                "Something went wrong retrieving an answer — please try again. "
                f"Details: {e}"
            )
        else:
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                    "tools_used": tools_used,
                    "stop_reason": stop_reason,
                }
            )
