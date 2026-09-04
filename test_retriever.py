# test_retriever.py
#
# Purpose: wrap the raw vector search (see test_search.py) into a proper
# LangChain retriever object, the form the rest of the pipeline (ask.py)
# actually consumes, and confirm both plain and filtered retrieval work
# before wiring in the LLM.

from dotenv import load_dotenv
from langchain_voyageai import VoyageAIEmbeddings
from langchain_chroma import Chroma

load_dotenv()

embeddings = VoyageAIEmbeddings(model="voyage-3")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)

# WHY THIS VALUE (k=4): this is a balance point, not a universal constant.
# Too low (k=1 or 2) and the assistant may miss relevant context split
# across multiple chunks (this project's cross-module questions needed
# several chunks combined to answer correctly). Too high and you start
# feeding the LLM irrelevant padding, which costs more tokens and can
# dilute the answer. 4 worked well for a ~49-chunk knowledge base; a much
# larger or smaller document may need a different number, worth testing a
# couple of values against your own hardest questions.
retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 4}
)

# Optional: a retriever that can narrow a search to one category/module,
# using the module_id metadata field set in add_metadata.py. This is
# entirely optional; skip or remove this if your document doesn't have
# natural categories worth filtering by. If you rename or restructure your
# metadata fields, update the "module_id" key below to match.
def get_retriever_for_query(module_id=None):
    search_kwargs = {"k": 4}
    if module_id:
        search_kwargs["filter"] = {"module_id": module_id}
    return vectorstore.as_retriever(search_type="similarity", search_kwargs=search_kwargs)

if __name__ == "__main__":
    # PROJECT SPECIFIC: swap this test question, and the "SAL" filter value
    # below, for something meaningful in your own document.
    question = "why is my order on hold"

    print("=== Plain retrieval (k=4, no filter) ===")
    results = retriever.invoke(question)
    for r in results:
        print(f"- {r.metadata['section_title']} ({r.metadata['module_id']})")

    print("\n=== Filtered retrieval (SAL module only) ===")
    sal_retriever = get_retriever_for_query(module_id="SAL")
    results = sal_retriever.invoke(question)
    for r in results:
        print(f"- {r.metadata['section_title']} ({r.metadata['module_id']})")

    # WHAT TO LOOK FOR: the filtered results should ALL show the module you
    # filtered on, and ideally cover that module's different subsections
    # (overview, process steps, statuses, etc.) rather than 4 near-identical
    # chunks. If filtering returns nothing, double check the module_id value
    # you're filtering on actually exists in your tagged chunks.
