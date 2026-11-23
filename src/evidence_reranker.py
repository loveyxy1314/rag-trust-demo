"""Experimental relevance ranking; scores do not establish truth or safety."""
import math

MODEL_ID='BAAI/bge-reranker-v2-m3'
REVISION='953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e'


def rank_candidates(items, scores, top_k=3, min_score=None):
    if type(top_k) is not int or top_k < 1:
        raise ValueError('top_k must be a positive integer')
    if len(items)!=len(scores):
        raise ValueError('one relevance score is required per candidate')
    if min_score is not None and not math.isfinite(float(min_score)):
        raise ValueError('threshold must be finite')
    values=[float(x) for x in scores]
    if any(not math.isfinite(x) for x in values):
        raise ValueError('nonfinite scores cannot be ranked')
    order=sorted(range(len(items)),key=lambda i:(-values[i],i))
    selected=[];audit=[]
    for index in order:
        item=items[index];score=values[index]
        reason='below_calibrated_threshold' if min_score is not None and score<min_score else 'outside_top_k' if len(selected)>=top_k else 'selected'
        audit.append({'source_candidate_id':item['id'],'doc_id':item['doc_id'],'score':score,'reason':reason})
        if reason=='selected':
            selected.append({**item,'source_candidate_id':item['id'],'id':len(selected)+1})
    return selected,audit


class RelevanceScorer:
    """Official Transformers cross-encoder path; no generative review prompt."""
    def __init__(self, device='cpu', fp16=False, max_length=512):
        import torch
        from transformers import AutoTokenizer,AutoModelForSequenceClassification
        self.torch=torch;self.device=device;self.max_length=max_length
        self.tokenizer=AutoTokenizer.from_pretrained(MODEL_ID,revision=REVISION,trust_remote_code=False)
        dtype=torch.float16 if fp16 else torch.float32
        self.model=AutoModelForSequenceClassification.from_pretrained(MODEL_ID,revision=REVISION,
            torch_dtype=dtype,trust_remote_code=False,use_safetensors=True).to(device).eval()

    def score(self, question, items, batch_size=8):
        if type(batch_size) is not int or batch_size<1:raise ValueError('batch_size must be positive')
        pairs=[[question,x['text']] for x in items]
        if not pairs:return []
        lengths=self.tokenizer(pairs,padding=False,truncation=False,add_special_tokens=True)['input_ids']
        if any(len(x)>self.max_length for x in lengths):
            raise ValueError('oversized question/passage pair; explicit handling required, no silent truncation')
        result=[]
        with self.torch.inference_mode():
            for start in range(0,len(pairs),batch_size):
                inputs=self.tokenizer(pairs[start:start+batch_size],padding=True,truncation=False,return_tensors='pt').to(self.device)
                logits=self.model(**inputs,return_dict=True).logits
                if logits.ndim!=2 or logits.shape[-1]!=1:raise ValueError('expected one relevance logit per pair')
                result.extend(logits[:,0].float().cpu().tolist())
        return result
