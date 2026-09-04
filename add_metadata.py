# add_metadata.py
#
# Purpose: tag each chunk with metadata (a section title, and a category/
# module label) so the retriever can later filter searches down to a
# specific area of the document, not just search everything blindly.
#
# BUG CONTEXT worth knowing before you adapt this: an earlier, simpler
# version of this only tagged a chunk with its module if the chunk's own
# text literally contained a line like "Module ID: SAL". That failed
# silently: only the ONE chunk that happened to contain that literal text
# got tagged correctly, while every other chunk under that same section
# (subsections, detail, tables) fell through to "general". The two-pass
# approach below fixes that by tagging based on SECTION NUMBER rather than
# literal text matching, so every subsection under a tagged section inherits
# the correct label. If you adapt this for your own document, keep this
# "tag by structural position, not by literal text" principle even if your
# specific module-marker format is different.

import re
from chunk_document import chunk_by_heading

def get_top_level_number(section_title):
    # Pulls the leading number off a heading, e.g. "6.2 Core Process" -> "6".
    # This assumes the same numbered-heading structure as chunk_document.py.
    # If you changed that chunking pattern, this needs to match it.
    match = re.match(r'^(\d+)\.', section_title)
    return match.group(1) if match else None

def add_metadata(chunks):
    # Pass 1: find which top-level section number belongs to which module,
    # by scanning for a literal marker line ("Module ID: X") and noting
    # which section number it appeared under.
    section_to_module = {}
    for chunk in chunks:
        first_line = chunk.split("\n")[0]
        top_level = get_top_level_number(first_line)
        # PROJECT SPECIFIC: this list of module codes (SAL, PUR, INV, MFG,
        # WH, FIN) is entirely specific to the Moore Foods ERP document
        # structure. Replace this with whatever categories make sense for
        # YOUR document, e.g. department names, product lines, chapter
        # topics, or drop the concept of "module" filtering entirely if your
        # document doesn't have natural categories like this.
        for mod in ["SAL", "PUR", "INV", "MFG", "WH", "FIN"]:
            if f"Module ID: {mod}" in chunk and top_level:
                section_to_module[top_level] = mod

    # Pass 2: tag every chunk, including subsections, using the section
    # number mapping built above rather than re-checking for the literal
    # marker text. Any section number not found in the mapping falls back to
    # "general" — for this project, that correctly captures the front
    # matter, cross-cutting sections, and anything not tied to one specific
    # module.
    tagged = []
    for chunk in chunks:
        first_line = chunk.split("\n")[0]
        top_level = get_top_level_number(first_line)
        module_id = section_to_module.get(top_level, "general")
        tagged.append({
            "text": chunk,
            "section_title": first_line,
            "module_id": module_id,
        })
    return tagged

if __name__ == "__main__":
    with open("knowledge_base.txt", encoding="utf-8") as f:
        text = f.read()
    chunks = chunk_by_heading(text)
    tagged_chunks = add_metadata(chunks)

    print(f"Tagged {len(tagged_chunks)} chunks.\n")

    module_counts = {}
    for tc in tagged_chunks:
        module_counts[tc["module_id"]] = module_counts.get(tc["module_id"], 0) + 1

    print("Chunks per module:")
    for mod, count in sorted(module_counts.items()):
        print(f"  {mod}: {count}")

    # SANITY CHECK WORTH KEEPING: if every chunk here shows the same module,
    # or "general" only, the section-number matching above likely isn't
    # lining up with your document's actual heading numbers.
    print("\nSample tagged chunks:")
    for tc in tagged_chunks[:5]:
        print(f"\n  section_title: {tc['section_title']}")
        print(f"  module_id: {tc['module_id']}")
