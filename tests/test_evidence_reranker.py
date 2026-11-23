import pytest
from src.evidence_reranker import rank_candidates
from src.evidence_selector import render

ITEMS=[{'id':1,'doc_id':'a','text':'第一段。'},{'id':2,'doc_id':'b','text':'第二段。'}]


def test_reordered_ids_are_contiguous_and_render_unchanged_source():
    selected,audit=rank_candidates(ITEMS,[-2,4],top_k=1)
    assert selected[0]['id']==1 and selected[0]['source_candidate_id']==2
    assert render('{"choice":1}',selected,{'a':'第一段。','b':'第二段。'})['answer']=='第二段。 [b]'
    assert audit[0]['score']==4 and ITEMS[1]['id']==2


def test_ranking_alone_has_no_implicit_rejection_threshold():
    selected,_=rank_candidates(ITEMS,[-200,-100])
    assert len(selected)==2


def test_explicit_threshold_can_produce_no_candidates():
    selected,audit=rank_candidates(ITEMS,[-2,-1],min_score=0)
    assert selected==[] and all(x['reason']=='below_calibrated_threshold' for x in audit)


@pytest.mark.parametrize('scores',[[1],[float('nan'),1],[1,float('inf')]])
def test_bad_scores_do_not_silently_rank(scores):
    with pytest.raises(ValueError):rank_candidates(ITEMS,scores)


def test_ties_keep_input_order_and_empty_inputs_are_valid():
    selected,_=rank_candidates(ITEMS,[1,1]);assert [x['doc_id'] for x in selected]==['a','b']
    assert rank_candidates([],[])==([],[])
