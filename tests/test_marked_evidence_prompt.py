import json
from src.marked_evidence_prompt import marked_messages
from src.evidence_selector import render


def test_marking_preserves_runtime_id_and_raw_output_provenance():
    case={'question':'问题？','contexts':{'d':'第一句。第二句。'},'reference':'SECRET'}
    items=[{'id':1,'doc_id':'d','text':'第一句。第二句。'}]
    msgs=marked_messages(case,items);payload=json.loads(msgs[1]['content'])
    assert payload['candidates'][0]['text'].count('[DATA_')==2
    assert payload['candidates'][0]['id']==1 and 'SECRET' not in str(msgs)
    assert render('{"choice":1}',items,case['contexts'])['answer']=='第一句。第二句。 [d]'
