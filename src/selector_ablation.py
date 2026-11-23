"""Frozen two-factor development experiment conditions."""
from .evidence_selector import candidates
from .evidence_guard import DIRECTIVE
from .paragraph_selector import build_candidates

CONDITIONS = ('sentence_unfiltered', 'sentence_filtered', 'paragraph_unfiltered', 'paragraph_filtered')


def build(contexts, condition):
    if condition not in CONDITIONS:
        raise ValueError('unknown condition')
    filtered = condition.endswith('_filtered')
    if condition.startswith('paragraph_'):
        return build_candidates(contexts, filter_directives=filtered)
    rejected = []
    accepted = {}
    for doc_id, text in contexts.items():
        if filtered and DIRECTIVE.search(text):
            rejected.append({'doc_id': doc_id, 'reason': 'directive_in_source_document'})
        else:
            accepted[doc_id] = text
    return candidates(accepted), rejected
