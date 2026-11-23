"""Development candidate builder preserving complete source paragraphs."""
import re
from .evidence_guard import DIRECTIVE

VERSION = 'paragraph-development-v1'


def build_candidates(contexts, max_chars=2000, filter_directives=True):
    """Return candidates and rejection audit; never truncate a paragraph.

    A directive rejects the entire source document before paragraph splitting.
    This conservative heuristic may reject legitimate discussions of attacks.
    """
    items, rejected = [], []
    for doc_id, text in contexts.items():
        if filter_directives and DIRECTIVE.search(text):
            rejected.append({'doc_id': doc_id, 'reason': 'directive_in_source_document'})
            continue
        for match in re.finditer(r'[^\r\n]+', text):
            paragraph = match.group().strip()
            if not paragraph:
                continue
            start = match.start() + len(match.group()) - len(match.group().lstrip())
            reason = None
            if paragraph.endswith(('?', '？')) and len(re.findall(r'[?？]', paragraph)) == 1:
                reason = 'question_only_or_ambiguous'
            elif len(paragraph) > max_chars:
                reason = 'paragraph_exceeds_limit'
            if reason:
                rejected.append({'doc_id': doc_id, 'start': start, 'reason': reason})
            else:
                items.append({'id': len(items) + 1, 'doc_id': doc_id, 'text': paragraph,
                              'start': start, 'end': start + len(paragraph)})
    return items, rejected
