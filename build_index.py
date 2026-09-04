# build_index.py
#
# Purpose: pull the pipeline together (load -> chunk -> tag) and turn the
# result into a searchable vector database (Chroma), by sending every chunk
# to an embedding model and persisting the result to disk.
#
# BUG CONTEXT worth knowing before you re-run this repeatedly: Chroma's
# from_documents(), when pointed at a persist_directory that already has
# data in it, ADDS the new documents on top of the old ones rather than
# replacing them. If you edit your source document and re-run this script,
# you will end up with duplicate, stale chunks silently mixed in with the
# fresh ones, and retrieval quality quietly degrades without any error being
# thrown. Delete the persist_directory folder (chroma_db by default) before
# every rebuild to avoid this. This script does NOT do that deletion for
# you, so it's worth adding a check or a manual step for it if you're
# adapting this for repeated use.

import os
from dotenv import load_dotenv
from langchain_voyageai import VoyageAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document as LC_Document

from load_document import load_docx_text
from chunk_document import chunk_by_heading
from add_metadata import add_metadata

load_dotenv()

def main():
    # PROJECT SPECIFIC: same hardcoded path as load_document.py, change it
    # to point at your own source document. If you have multiple source
    # documents, this is the spot to loop over a folder and combine chunks
    # from all of them (tagging each chunk with which document it came from,
    # in addition to its module/category, would be worth adding at that
    # point).
    text = load_docx_text("Data/Moore_Foods_ERP_Process_Knowledge_Base_v3.docx")
    chunks = chunk_by_heading(text)
    tagged_chunks = add_metadata(chunks)

    docs = [
        LC_Document(
            page_content=tc["text"],
            # Whatever fields you tag in add_metadata.py end up here as
            # searchable/filterable metadata. If you added or renamed
            # fields there, update this dict to match.
            metadata={"section_title": tc["section_title"], "module_id": tc["module_id"]}
        )
        for tc in tagged_chunks
    ]

    # WHY THIS MODEL: voyage-3 is Voyage AI's general purpose embedding
    # model at the time this was built. If cost, speed, or embedding quality
    # matters differently for your use case, check Voyage's current model
    # lineup, this is a one-line swap.
    embeddings = VoyageAIEmbeddings(model="voyage-3")

    # persist_directory="./chroma_db" is where the vector database gets
    # written to disk. See the BUG CONTEXT note at the top of this file
    # before re-running this against an existing folder.
    vectorstore = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory="./chroma_db",
    )
    print(f"Indexed {len(docs)} chunks into ./chroma_db")

if __name__ == "__main__":
    main()
