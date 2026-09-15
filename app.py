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

# The chat input box, pinned to the bottom of the page by Streamlit.
user_question = st.chat_input("Ask a question")

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
