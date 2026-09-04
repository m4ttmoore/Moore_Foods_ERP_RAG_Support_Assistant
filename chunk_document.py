# chunk_document.py
#
# Purpose: split the extracted plain text into chunks small enough for good
# retrieval, but large enough to keep useful context together.
#
# The approach here is HEADING BASED chunking: it splits wherever it sees a
# line that looks like a numbered heading ("6. Sales & Distribution" or
# "6.2 Core Process"). This only works well if your source document is
# actually WRITTEN with consistent numbered headings throughout. If your
# document doesn't have that structure, this whole function needs a
# different splitting strategy, e.g. fixed character length, sentence
# boundaries, or a different heading pattern (bullet points, all-caps
# titles, markdown-style "#" headers, etc.).

import re

def chunk_by_heading(text):
    # PROJECT SPECIFIC / ADAPT THIS PATTERN:
    # Matches a line starting with digits, one or more optional ".digits"
    # groups, then a space and a capital letter — e.g. "6.", "6.2", "6.10".
    # If your document numbers headings differently (letters, Roman
    # numerals, "Section 6:" style, no numbering at all), this regex is the
    # one thing you need to rewrite for your own project.
    pattern = r'\n(?=\d+\.\d*\.?\d*\s+[A-Z])'
    raw_chunks = re.split(pattern, text)

    # WHY THIS VALUE (20 characters): filters out near-empty fragments left
    # over from the split (e.g. a lone heading with nothing after it before
    # the next split point). If you switch to a different chunking strategy
    # with naturally shorter/longer pieces, this threshold may need
    # adjusting too.
    chunks = [c.strip() for c in raw_chunks if len(c.strip()) > 20]
    return chunks

if __name__ == "__main__":
    # encoding="utf-8" required here too, see load_document.py for why.
    with open("knowledge_base.txt", encoding="utf-8") as f:
        text = f.read()
    chunks = chunk_by_heading(text)
    print(f"Created {len(chunks)} chunks.")

    # SANITY CHECK WORTH KEEPING: if this number looks wildly wrong (5 chunks
    # for a long document, or hundreds for a short one), your heading pattern
    # above almost certainly isn't matching your document's actual heading
    # style. This was the single most common thing to get wrong when this
    # script was first built.
    for i, c in enumerate(chunks[:3]):
        print(f"\n--- Chunk {i} ---\n{c[:200]}...")
