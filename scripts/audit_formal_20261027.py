"""Read-only independent audit; derived files go to a separate review folder."""
import collections
import csv
import hashlib
import itertools
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_rows(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8-sig').splitlines() if s.strip()]


def write_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ['status'])
        w.writeheader()
        w.writerows(rows)


def audit():
    run = ROOT/'results/formal_20261027'
    out = ROOT/'results/review_20261027'
    out.mkdir(exist_ok=True)
    raw = read_rows(run/'raw.jsonl')
    evaluations = read_rows(run/'detect_eval.jsonl')
    docs = read_rows(ROOT/'data/dataset/corpus.jsonl')
    poison = read_rows(ROOT/'data/dataset/poison.jsonl')
    queries = read_rows(ROOT/'data/dataset/queries.jsonl')
    meta = json.loads((run/'meta.json').read_text(encoding='utf8'))
    key = lambda r: (r['scene'], r['poisoning_ratio'], r['group'], r['query_id'])
    expected = set(itertools.product(meta['scenes'], meta['ratios'], meta['groups'], [q['query_id'] for q in queries]))
    keys = [key(r) for r in raw]
    assert len(keys) == len(set(keys)) == 768 and set(keys) == expected
    assert len(evaluations) == 1200 and not any(r['error'] for r in raw)
    h = lambda text: hashlib.sha256(text.encode('utf8')).hexdigest()
    hashes = {
        'doc_sha256': h('\n'.join(sorted(d['doc_id'] + h(d['text']) for d in docs))),
        'poison_sha256': h('\n'.join(sorted(d['doc_id'] + h(d['text']) for d in poison))),
        'queries_sha256': h(json.dumps(queries, ensure_ascii=False, sort_keys=True)),
    }
    assert all(v == meta['dataset_meta'][k] for k, v in hashes.items())
    grouped = collections.defaultdict(list)
    for row in raw:
        grouped[key(row)[:3]].append(row)
    summaries = []
    for (scene, ratio, group), rows in sorted(grouped.items()):
        attacked = sum(bool(r['malicious_retrieved']) for r in rows)
        exposed = sum(bool(r['malicious_accepted']) for r in rows)
        success = sum(bool(r['attack_success']) and bool(r['malicious_retrieved']) for r in rows)
        summaries.append(dict(scene=scene, ratio=ratio, group=group, n=len(rows), attacked=attacked,
            exposed=exposed, marker_success=success, marker_asr=success/attacked if attacked else None,
            rule_correct=sum(r['answer_correct'] for r in rows),
            rule_accuracy=sum(r['answer_correct'] for r in rows)/len(rows),
            normal_review_occurrences=sum(len(r['normal_reviewed']) for r in rows),
            normal_review_unique=len({d for r in rows for d in r['normal_reviewed']}),
            empty_contexts=sum(r['context_count']==0 for r in rows),
            insufficient_answers=sum(r['answer'].strip().rstrip('。.!！')=='证据不足' for r in rows),
            mean_total_s=sum(r['total_s'] for r in rows)/len(rows)))
    write_csv(out/'condition_audit.csv', summaries)
    published = list(csv.DictReader((run/'summary.csv').open(encoding='utf-8-sig')))
    pub = {(r['scene'], float(r['poisoning_ratio']), r['group']): r for r in published}
    for r in summaries:
        p = pub[(r['scene'],r['ratio'],r['group'])]
        assert abs(float(p['answer_accuracy'])-r['rule_accuracy']) < 0.000051
        assert int(p['attacked_queries']) == r['attacked']
        assert int(p['attack_success']) == r['marker_success']
    query_map = {q['query_id']: q for q in queries}
    qa_groups = collections.defaultdict(list)
    support_groups = collections.defaultdict(list)
    for r in raw:
        qa_groups[(r['query_id'], r['answer'])].append(r)
        support_groups[(r['query_id'], r['answer'], json.dumps(r['context_texts'], ensure_ascii=False, sort_keys=True))].append(r)
    qa_queue=[]; mapping=[]
    for (qid,answer), rows in sorted(qa_groups.items()):
        ident = h(qid+'\0'+answer)[:16]
        qa_queue.append(dict(answer_id=ident,question=query_map[qid]['question'],reference=query_map[qid]['reference'],
            answer=answer,human_correct='',human_semantic_target_achieved='',reviewer='',notes=''))
        mapping.append(dict(answer_id=ident,query_id=qid,occurrences=len(rows),
            conditions=[list(key(r)) for r in rows],rule_correct=rows[0]['answer_correct']))
    write_csv(out/'answer_review_queue.csv',qa_queue)
    citation_rows=[]; support_queue=[]
    for (qid,answer,context_json),rows in sorted(support_groups.items()):
        context=json.loads(context_json)
        cited=sorted(set(re.findall(r'\bn-[A-Za-z0-9_-]+',answer)))
        outside=sorted(set(cited)-set(context))
        ident=h(qid+'\0'+answer+'\0'+context_json)[:16]
        citation_rows.append(dict(support_id=ident,query_id=qid,occurrences=len(rows),
            cited_ids=';'.join(cited),outside_context=';'.join(outside)))
        support_queue.append(dict(support_id=ident,question=query_map[qid]['question'],answer=answer,
            contexts=context,human_claim_supported=None,human_citations_valid=None,notes=''))
    write_csv(out/'citation_audit.csv',citation_rows)
    (out/'answer_condition_mapping.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2),encoding='utf8')
    (out/'support_review_queue.json').write_text(json.dumps(support_queue,ensure_ascii=False,indent=2),encoding='utf8')
    diagnostic=dict(records=len(raw),unique_keys=len(set(keys)),conditions=len(grouped),queries=len(queries),errors=0,
        document_evaluations=len(evaluations),clean_docs=len(docs),poison_pool=len(poison),fact_clusters=len({d['fact_id'] for d in docs}),
        normal_with_literal_reference=sum(d['reference'] in d['text'] for d in docs),
        train_test_shared_facts=len({d['fact_id'] for d in docs if d['split']=='train'} & {d['fact_id'] for d in docs if d['split']=='test'}),
        unique_malicious_evaluated_ids=len({e['doc_id'] for e in evaluations if e['label_eval']=='malicious'}),
        evaluated_malicious_fact_clusters=len({e['doc_id'].rsplit('-',1)[0] for e in evaluations if e['label_eval']=='malicious'}),
        eval_cache_hits=sum(e['cache_hit'] for e in evaluations),eval_cold_rows=sum(not e['cache_hit'] for e in evaluations),
        initially_clean_eval_cache_hits=sum(e['cache_hit'] for e in evaluations if e['poisoning_ratio']==0),
        unique_question_answers=len(qa_queue),unique_question_answer_contexts=len(support_queue),
        contexts_with_explicit_ids=sum(bool(r['cited_ids']) for r in citation_rows),
        contexts_with_outside_ids=sum(bool(r['outside_context']) for r in citation_rows),
        pending_automatic_review_rows=len(list(csv.DictReader((run/'manual_review.csv').open(encoding='utf-8-sig')))),
        data_hashes=hashes,
        original_artifact_sha256={name:hashlib.sha256((run/name).read_bytes()).hexdigest() for name in ['raw.jsonl','detect_eval.jsonl','meta.json','summary.csv']},
        boundary='No new model inference, manual grades, or changes to original formal artifacts. Queue labels are blank.')
    (out/'audit.json').write_text(json.dumps(diagnostic,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(diagnostic,ensure_ascii=False,indent=2))


if __name__=='__main__':
    audit()
