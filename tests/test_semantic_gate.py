import json
import pytest
from src.semantic_gate import gate_messages, apply_gate

BASE={'decision':'answer','choice':1,'answer':'原文。 [opaque]',
      'evidence':{'id':1,'doc_id':'opaque','text':'原文。'}}


def test_acceptance_preserves_original_answer_and_evidence():
    r=apply_gate(BASE,'{"choice":1}')
    assert r['answer']==BASE['answer'] and r['evidence']==BASE['evidence']
    assert 'gate_status' not in BASE


@pytest.mark.parametrize('raw',['{"choice":true}','{"choice":2}','{"choice":1,"reason":"yes"}','null',None,'not json'])
def test_invalid_gate_output_never_accepts(raw):
    assert apply_gate(BASE,raw)['decision']=='review'


def test_rejection_retains_evidence_for_audit_without_answering():
    r=apply_gate(BASE,'{"choice":0}')
    assert r['decision']=='abstain' and r['rejected_evidence']==BASE['evidence']


def test_program_refusal_is_not_a_model_gate_refusal():
    r=apply_gate({'decision':'abstain','answer':'证据不足','choice':0},None)
    assert r['gate_status']=='not_applicable'


def test_model_input_contains_only_question_and_evidence_no_evaluation_metadata():
    base={**BASE,'label':'SECRET_LABEL','reference':'SECRET_REFERENCE'}
    msg=gate_messages('问题',base)
    assert set(json.loads(msg[1]['content']))=={'question','evidence'}
    assert 'SECRET' not in str(msg) and 'opaque' not in str(msg)
