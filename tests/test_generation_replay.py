from src.generation_replay import messages_for,EXTRACTIVE_INSTRUCTION
from src.rag_pipeline import GENERATOR_SYSTEM


def test_replay_inputs_exclude_reference_answers_and_grades():
    row=dict(case_id='SECRET_ID',question='Q',contexts={'n-one':'技术原句'},reference='SECRET_REF',answer='SECRET_ANSWER',evaluation_only='SECRET_LABEL')
    for variant in ['original','extractive']:
        messages=messages_for(row,variant)
        assert 'SECRET' not in str(messages)
        assert '[n-one] 技术原句' in messages[1]['content']


def test_replay_isolates_system_instruction_with_same_user_context():
    case=dict(question='Q',contexts={'n-one':'first','n-two':'second'})
    a=messages_for(case,'original');b=messages_for(case,'extractive')
    assert a[1]==b[1]
    assert a[0]['content']==GENERATOR_SYSTEM
    assert b[0]['content']==GENERATOR_SYSTEM+EXTRACTIVE_INSTRUCTION
