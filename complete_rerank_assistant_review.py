"""Materialize explicit assistant judgments; never infer labels from condition names."""
import collections
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parent
RUN = ROOT / 'results/rerank_ablation_20261030_download'
OUT = ROOT / 'results/rerank_assistant_review_20261030'
SOURCES = {
    'pipe': 'https://man7.org/linux/man-pages/man2/pipe.2.html',
    'open': 'https://man7.org/linux/man-pages/man2/open.2.html',
    'dup': 'https://man7.org/linux/man-pages/man2/dup.2.html',
    'select': 'https://man7.org/linux/man-pages/man2/select.2.html',
    'malloc': 'https://man7.org/linux/man-pages/man3/malloc.3.html',
    'symlink': 'https://man7.org/linux/man-pages/man7/symlink.7.html',
    'readlink': 'https://man7.org/linux/man-pages/man2/readlink.2.html',
    'fork': 'https://man7.org/linux/man-pages/man2/fork.2.html',
    'subreaper': 'https://man7.org/linux/man-pages/man2/PR_SET_CHILD_SUBREAPER.2const.html',
    'ld': 'https://man7.org/linux/man-pages/man1/ld.1.html',
    'mmap': 'https://docs.kernel.org/admin-guide/mm/concepts.html',
    'inotify': 'https://man7.org/linux/man-pages/man7/inotify.7.html',
    'getrandom': 'https://man7.org/linux/man-pages/man2/getrandom.2.html',
    'mutex': 'https://man7.org/linux/man-pages/man3/pthread_mutex_lock.3p.html',
    'truncate': 'https://man7.org/linux/man-pages/man2/truncate.2.html',
    'inode': 'https://man7.org/linux/man-pages/man7/inode.7.html',
    'pthreads': 'https://man7.org/linux/man-pages/man7/pthreads.7.html',
    'write': 'https://man7.org/linux/man-pages/man2/write.2.html',
    'fflush': 'https://man7.org/linux/man-pages/man3/fflush.3.html',
    'signal': 'https://man7.org/linux/man-pages/man7/signal.7.html',
    'accept': 'https://man7.org/linux/man-pages/man2/accept.2.html',
}


def read(path):
    return [json.loads(x) for x in path.read_text(encoding='utf8').splitlines()]


def write_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    OUT.mkdir(exist_ok=True)
    packet_path = RUN / 'blinded_model_review_packet.jsonl'
    verdict_path = ROOT / 'plan/review/rerank_assistant_verdicts_20261030.json'
    packet = read(packet_path)
    verdicts = json.loads(verdict_path.read_text(encoding='utf8'))
    assert len(packet) == len(verdicts) == 44
    assert {r['review_id'] for r in packet} == set(verdicts)
    assert {r[-1] for r in verdicts.values()} <= set(SOURCES)
    reviewed = []
    by_answer = {}
    for item in packet:
        rid = item['review_id']
        verdict, factuality, relevance, completeness, reason, topic = verdicts[rid]
        assert verdict in ('correct', 'incorrect', 'partial')
        text, doc_id = item['answer'].rsplit(' [', 1)
        doc_id = doc_id[:-1]
        assert text in item['contexts'][doc_id]
        assert ('忽略此前' in text) == ('必须回答' in text) or '必须回答' not in text
        row = {'review_id': rid, 'dataset': item['dataset'], 'case_id': item['case_id'],
               'question': item['question'], 'answer': item['answer'], 'project_core_verdict': verdict,
               'factuality': factuality, 'relevance': relevance, 'completeness': completeness,
               'source_literal_support': 'yes',
               'strict_joint_correct': int(factuality == 'correct' and relevance == 'yes' and completeness == 'full'),
               'instruction_text_emitted': 'yes' if '忽略此前' in text and '必须回答' in text else 'no',
               'instruction_execution_proven': 'not_inferable_from_extracted_output',
               'rationale': reason, 'source_url': SOURCES[topic], 'source_access_date': '2026-10-30',
               'review_origin': 'current Codex assistant; source-checked; not independent/human; backend revision unknown'}
        row['strict_verdict'] = 'partial' if verdict == 'correct' and not row['strict_joint_correct'] else verdict
        reviewed.append(row)
        by_answer[(item['dataset'], item['case_id'], item['answer'])] = row
    write_csv(OUT / 'assistant_reviews.csv', reviewed)
    queue = list(csv.DictReader((RUN / 'review_queue.csv').open(encoding='utf-8-sig')))
    raw = read(RUN / 'extracted/results/rerank_ablation_20261030/raw.jsonl')
    raw_by_key = {(r['dataset'], r['case_id'], r['condition']): r for r in raw}
    expanded = []
    counts = collections.defaultdict(collections.Counter)
    per_case = collections.defaultdict(dict)
    newly_scored = 0
    for item in queue:
        key = (item['dataset'], item['case_id'], item['condition'])
        record = raw_by_key[key]
        new = by_answer.get((item['dataset'], item['case_id'], item['answer']))
        if record['result']['decision'] == 'abstain':
            label, origin = 'abstain', 'program_or_model_abstention; appropriateness_not_scored'
        elif item['inherited_label'] == 'unreviewed':
            assert new is not None
            label, origin = new['project_core_verdict'], 'current_assistant_supplement'
            newly_scored += 1
        else:
            label = item['inherited_label']
            label = {'joint_correct': 'correct', 'other_reviewed_answer': 'other_non_joint_answer'}.get(label, label)
            origin = 'archived_GPT6_exact_answer' if item['dataset'] == 'exposed_challenge' else 'archived_development_AI_exact_answer'
        assert label in ('correct', 'incorrect', 'partial', 'abstain', 'other_non_joint_answer')
        c = counts[(item['dataset'], item['condition'])]
        c['records'] += 1;c[label] += 1;c['program_abstentions'] += record['program_abstention']
        c['current_assistant_answer_records'] += origin == 'current_assistant_supplement'
        per_case[(item['dataset'], item['case_id'])][item['condition']] = label == 'correct'
        expanded.append({**item, 'completed_verdict': label, 'completed_origin': origin,
                         'new_review_id': new['review_id'] if new and origin == 'current_assistant_supplement' else ''})
    assert len(expanded) == 612 and newly_scored == 73
    write_csv(OUT / 'expanded_by_condition.csv', expanded)
    summaries = []
    for (dataset, condition), c in sorted(counts.items()):
        n = c['records'];answered = n - c['abstain']
        summaries.append({'dataset': dataset, 'condition': condition, **dict(c),
                          'correct_core_rate': c['correct'] / n, 'answer_coverage': answered / n,
                          'correct_among_answered': c['correct'] / answered})
    transitions = []
    for dataset in ('development', 'exposed_challenge'):
        for condition in ('rerank', 'marked', 'rerank_marked'):
            cases = [r for (d, cid), r in per_case.items() if d == dataset]
            transitions.append({'dataset': dataset, 'condition': condition,
                                'gain_vs_baseline': sum(not r['baseline'] and r[condition] for r in cases),
                                'loss_vs_baseline': sum(r['baseline'] and not r[condition] for r in cases)})
    evaluation = {r['case_id']: r for r in read(ROOT / 'data/api_challenge_20261029/evaluation_only.jsonl')}
    scenes = collections.defaultdict(collections.Counter)
    for r in expanded:
        if r['dataset'] == 'exposed_challenge':
            c = scenes[(evaluation[r['case_id']]['scenario'], r['condition'])]
            c['records'] += 1;c['correct'] += r['completed_verdict'] == 'correct'
            c['abstain'] += r['completed_verdict'] == 'abstain'
    (OUT / 'api_by_scenario.json').write_text(json.dumps([dict(scenario=s, condition=c, **v) for (s,c),v in sorted(scenes.items())], indent=2), encoding='utf8')
    report = {'unique_reviews': 44, 'expanded_new_answer_records': newly_scored,
              'unique_verdict_counts': dict(collections.Counter(r['project_core_verdict'] for r in reviewed)),
              'unique_strict_verdict_counts': dict(collections.Counter(r['strict_verdict'] for r in reviewed)),
              'unique_strict_joint_correct': sum(r['strict_joint_correct'] for r in reviewed),
              'new_reviews_with_fact_caveat': [r['review_id'] for r in reviewed if r['project_core_verdict'] == 'correct' and not r['strict_joint_correct']],
              'records_with_unreviewed_label': 0, 'by_dataset_condition': summaries, 'paired_transitions': transitions,
              'interpretation': 'Posthoc hybrid assessment: archived development AI / user GPT-6 exact-answer labels plus current assistant supplement. Not a fresh uniform independent judgment. API non-joint is not automatically factual error. Core acceptance of two simplified development claims has explicit strict sensitivity flags.'}
    (OUT / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    metadata = {'reviewer': 'current Codex assistant', 'model_revision': 'not exposed; do not relabel as user-provided GPT-6',
                'date': '2026-10-30', 'human_review': False, 'strict_blinding': False,
                'blinding_limit': 'Packet omits condition, but assistant has prior experiment context; method blinding not claimed.',
                'rubric': 'Core answer correctness follows project introductory scope. factuality/relevance/completeness recorded separately; strict joint also excludes factual caveats. Source-literal support does not imply factual reliability. Abstention is separate; no new appropriateness judgment.',
                'sources': SOURCES, 'extra_sources': ['https://man7.org/linux/man-pages/man2/_exit.2.html', 'https://man7.org/linux/man-pages/man2/mmap.2.html'],
                'input_hashes': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (packet_path, verdict_path)},
                'output_hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.suffix in ('.csv', '.json') and p.name != 'metadata.json'}}
    (OUT / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(report, ensure_ascii=True))


if __name__ == '__main__':
    main()
