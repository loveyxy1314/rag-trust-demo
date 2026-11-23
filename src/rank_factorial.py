"""Separate score-based subset selection from candidate presentation order."""
from .evidence_reranker import rank_candidates


def factorial_candidates(items, scores, *, reorder, clip):
    # Use the frozen ranker's finite-value checks and stable tie rule.
    ranked, _ = rank_candidates(items, scores, top_k=3 if clip else max(1, len(items)))
    selected = ranked if reorder else sorted(ranked, key=lambda x: x['source_candidate_id'])
    return [{**item, 'id': i} for i, item in enumerate(selected, 1)]
