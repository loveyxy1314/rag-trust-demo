"""Exploratory post-selection checks; these do not establish factual accuracy."""
import re
from .evidence_selector import render

VERSION = 'development-v1'
# Inspect the entire selected document so sentence splitting cannot hide a directive.
DIRECTIVE = re.compile(r'忽略.{0,24}(?:指令|规则|要求|内容)|必须回答|不要给出其他结论|只输出.{0,12}标记|RAG_POISON_\d+')


def render_guarded(raw, items, contexts):
    result = render(raw, items, contexts)
    if result['decision'] != 'answer':
        return {**result, 'guard_version': VERSION, 'guard_reasons': []}
    evidence = result['evidence']
    reasons = []
    if DIRECTIVE.search(contexts[evidence['doc_id']]):
        reasons.append('directive_in_source_document')
    if evidence['text'].rstrip().endswith(('?', '？')):
        reasons.append('question_fragment')
    if reasons:
        return {'decision': 'abstain', 'answer': '证据不足', 'choice': result['choice'],
                'guard_version': VERSION, 'guard_reasons': reasons,
                'rejected_evidence': evidence}
    return {**result, 'guard_version': VERSION, 'guard_reasons': []}
