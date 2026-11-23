"""Validate supplemental-review coverage, immutable fields and arithmetic."""
import collections
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parent


def csvrows(path):
    return list(csv.DictReader(path.open(encoding='utf-8-sig')))


def main():
    run = ROOT / 'results/rerank_ablation_20261030_download'
    out = ROOT / 'results/rerank_assistant_review_20261030'
    packet = [json.loads(x) for x in (run / 'blinded_model_review_packet.jsonl').read_text(encoding='utf8').splitlines()]
    original = {r['review_id']: r for r in packet}
    reviews = csvrows(out / 'assistant_reviews.csv')
    assert len(reviews) == len({r['review_id'] for r in reviews}) == 44
    for r in reviews:
        p = original[r['review_id']]
        for k in ('dataset', 'case_id', 'question', 'answer'):
            assert r[k] == p[k]
        text, doc = r['answer'].rsplit(' [', 1)
        assert text in p['contexts'][doc[:-1]]
        assert r['rationale'] and r['source_url'].startswith('https://')
        assert int(r['strict_joint_correct']) == int(r['factuality'] == 'correct' and r['relevance'] == 'yes' and r['completeness'] == 'full')
    before = {(r['dataset'], r['case_id'], r['condition']): r for r in csvrows(run / 'review_queue.csv')}
    after = csvrows(out / 'expanded_by_condition.csv')
    assert len(after) == len({(r['dataset'], r['case_id'], r['condition']) for r in after}) == 612
    for r in after:
        b = before[(r['dataset'], r['case_id'], r['condition'])]
        assert all(r[k] == v for k, v in b.items())
        assert r['completed_verdict'] != 'unreviewed'
        if r['completed_origin'] == 'current_assistant_supplement':
            assert r['new_review_id'] in original
    summary = json.loads((out / 'summary.json').read_text(encoding='utf8'))
    assert summary['expanded_new_answer_records'] == sum(r['completed_origin'] == 'current_assistant_supplement' for r in after) == 73
    assert summary['unique_verdict_counts'] == dict(collections.Counter(r['project_core_verdict'] for r in reviews))
    for s in summary['by_dataset_condition']:
        rows = [r for r in after if (r['dataset'], r['condition']) == (s['dataset'], s['condition'])]
        c = collections.Counter(r['completed_verdict'] for r in rows)
        assert s['records'] == len(rows) and all(s[k] == v for k, v in c.items())
        assert s['correct_core_rate'] == c['correct'] / len(rows)
    meta = json.loads((out / 'metadata.json').read_text(encoding='utf8'))
    for path, sha in meta['input_hashes'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha
    for name, sha in meta['output_hashes'].items():
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == sha
    assert meta['human_review'] is False and meta['strict_blinding'] is False
    print('Verified: 44 unique source-cited reviews, 73 mapped answers, 612 covered records, immutable fields, verdict totals and SHA256 hashes.')


if __name__ == '__main__':
    main()
