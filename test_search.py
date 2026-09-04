# test_search.py
#
# Purpose: a quick, minimal sanity check that the vector database built by
# build_index.py actually retrieves sensible, relevant results, BEFORE you
# build anything more complex (a retriever wrapper, the full assistant) on
# top of it. Cheap to run, fast to eyeball.

from dotenv import load_dotenv
from langchain_voyageai import VoyageAIEmbeddings
from langchain_chroma import Chroma

load_dotenv()

# Must match the embedding model used in build_index.py. If these two ever
# get out of sync (e.g. you change the model in one file but not the other),
# retrieval quality silently degrades rather than throwing a clear error, so
# keep them matched.
embeddings = VoyageAIEmbeddings(model="voyage-3")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)

# PROJECT SPECIFIC: swap this for a question you actually know the correct
# answer to in YOUR document, so you can visually confirm the top result is
# the right one. k=3 here (fewer than the k=4 used elsewhere) is
# intentional, this script is just a quick look, not the real retrieval
# configuration.
results = vectorstore.similarity_search("why is my order on hold", k=3)
for r in results:
    print("---")
    print(r.metadata)
    print(r.page_content[:200])

# WHAT TO LOOK FOR: the top result's section_title/module_id (from
# add_metadata.py) should obviously match the topic of your test question.
# If it doesn't, or if you see the exact same chunk repeated more than once
# in the results, that repetition is the signature of the duplicate-index
# bug described in build_index.py, re-run this after deleting and rebuilding
# chroma_db from scratch.
