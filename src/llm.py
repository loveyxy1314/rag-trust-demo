"""Local causal-LM wrapper (Transformers + ROCm/CUDA)."""
from __future__ import annotations

import time

import torch


class LocalLLM:
    def __init__(self, model_id: str, dtype: str = "float16", device: str = "cuda", revision: str | None = None):
        from transformers import AutoModelForCausalLM, AutoTokenizer

        torch_dtype = getattr(torch, dtype, torch.float16)
        self.model_id = model_id
        self.revision = revision
        self.device = device if torch.cuda.is_available() else "cpu"
        load_start = time.perf_counter()
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision, trust_remote_code=False)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        kwargs = dict(trust_remote_code=False)
        try:
            self.model = AutoModelForCausalLM.from_pretrained(model_id, dtype=torch_dtype, revision=revision, **kwargs)
        except TypeError:  # older transformers
            self.model = AutoModelForCausalLM.from_pretrained(
                model_id, torch_dtype=torch_dtype, revision=revision, **kwargs
            )
        self.model = self.model.to(self.device).eval()
        self.load_seconds = time.perf_counter() - load_start
        self.dtype = str(next(self.model.parameters()).dtype)

    def generate(self, messages: list[dict], max_new_tokens: int = 128, temperature: float = 0.0) -> tuple[str, float]:
        if hasattr(self.tokenizer, "apply_chat_template") and self.tokenizer.chat_template:
            encoded = self.tokenizer.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=True, return_tensors="pt", return_dict=True
            )
        else:  # pragma: no cover - fallback for base models
            prompt = "\n".join(m["content"] for m in messages)
            encoded = self.tokenizer(prompt, return_tensors="pt")
        encoded = {k: v.to(self.device) for k, v in encoded.items()}
        if self.device == "cuda":
            torch.cuda.synchronize()
        start = time.perf_counter()
        with torch.inference_mode():
            output = self.model.generate(
                **encoded,
                max_new_tokens=max_new_tokens,
                do_sample=temperature > 0,
                temperature=temperature if temperature > 0 else None,
                pad_token_id=self.tokenizer.pad_token_id,
            )
        if self.device == "cuda":
            torch.cuda.synchronize()
        seconds = time.perf_counter() - start
        prompt_len = encoded["input_ids"].shape[1]
        text = self.tokenizer.decode(output[0, prompt_len:], skip_special_tokens=True)
        return text.strip(), seconds

    def warmup(self) -> float:
        _, seconds = self.generate([{"role": "user", "content": "只回复 OK。"}], max_new_tokens=4)
        return seconds

    @property
    def memory_report(self) -> dict:
        info = {"model": self.model_id, "revision": self.revision, "dtype": self.dtype, "device": self.device}
        if self.device == "cuda":
            info.update(
                gpu=torch.cuda.get_device_name(0),
                allocated_mb=round(torch.cuda.memory_allocated() / 2**20, 1),
                max_allocated_mb=round(torch.cuda.max_memory_allocated() / 2**20, 1),
            )
        return info
