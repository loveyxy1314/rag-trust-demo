import copy
from src.rank_factorial import factorial_candidates
from src.evidence_selector import render


def test_order_and_subset_are_independent_and_source_stays_immutable():
    items = [{'id': i, 'doc_id': str(i), 'text': str(i)} for i in range(1, 6)]
    original = copy.deepcopy(items)
    scores = [1, 5, 0, 4, 3]
    expected = {(False, False): ['1','2','3','4','5'], (True, False): ['2','4','5','1','3'],
                (False, True): ['2','4','5'], (True, True): ['2','4','5']}
    for (order, clip), docs in expected.items():
        selected = factorial_candidates(items, scores, reorder=order, clip=clip)
        assert [x['doc_id'] for x in selected] == docs
        assert [x['id'] for x in selected] == list(range(1, len(selected)+1))
        for i, item in enumerate(selected, 1):
            assert render('{"choice":'+str(i)+'}', selected, {x['doc_id']:x['text'] for x in items})['answer'] == item['text']+' ['+item['doc_id']+']'
    assert items == original


def test_clipping_preserves_original_order_even_when_scores_disagree():
    items = [{'id':i, 'doc_id':str(i), 'text':str(i)} for i in range(1,5)]
    clipped = factorial_candidates(items, [4,0,5,3], reorder=False, clip=True)
    assert [x['source_candidate_id'] for x in clipped] == [1,3,4]


def test_ties_short_lists_and_empty_inputs():
    items = [{'id':1, 'doc_id':'a', 'text':'a'}, {'id':2, 'doc_id':'b', 'text':'b'}]
    assert [x['doc_id'] for x in factorial_candidates(items, [1,1], reorder=True, clip=True)] == ['a','b']
    assert factorial_candidates([], [], reorder=True, clip=True) == []
