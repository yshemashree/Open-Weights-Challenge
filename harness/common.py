"""Shared pieces: fixed prompt, fixed tools, model backends. Stdlib only."""
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = json.loads((ROOT / "schemas" / "tools.json").read_text())
TOOL_NAMES = {t["name"] for t in TOOLS}
SYSTEM_TEMPLATE = (ROOT / "prompts" / "system_prompt.txt").read_text()

LENDER = "Suvidha Finance"  # fictional
# Relative dates ("kal", "parso", "Saturday") need an anchor. This line is the only
# addition to the baseline prompt, and it is identical for every model and case.
DATE_CONTEXT = "Call context: today is Thursday, 2026-10-01. Current time 11:00 IST."

PROFILES = {
    "R": {"NAME": "Rahul Sharma", "DPD": 5, "PRODUCT": "personal loan", "AMOUNT": 12500},
    "P": {"NAME": "Priya Deshmukh", "DPD": 30, "PRODUCT": "two-wheeler loan", "AMOUNT": 8400},
    "A": {"NAME": "Amit Verma", "DPD": 90, "PRODUCT": "credit card", "AMOUNT": 46000},
    "S": {"NAME": "Sneha Patil", "DPD": 30, "PRODUCT": "consumer durable loan", "AMOUNT": 6200},
}


def system_prompt(profile_key):
    p = PROFILES[profile_key]
    return (SYSTEM_TEMPLATE
            .replace("{LENDER}", LENDER)
            .replace("{NAME}", p["NAME"])
            .replace("{DPD}", str(p["DPD"]))
            .replace("{PRODUCT}", p["PRODUCT"])
            .replace("{AMOUNT}", f"₹{p['AMOUNT']:,}"))


def build_messages(case):
    msgs = [{"role": "system", "content": system_prompt(case["profile"]) + "\n" + DATE_CONTEXT}]
    msgs += case["history"]
    msgs.append({"role": "user", "content": case["borrower_turn"]})
    return msgs


def load_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _post(url, payload, headers=None, timeout=600):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _norm_calls(raw_calls):
    """Normalise tool calls to [{name, arguments_raw, arguments, parse_ok}]."""
    out = []
    for c in raw_calls or []:
        fn = c.get("function", c)
        args = fn.get("arguments")
        if isinstance(args, dict):
            out.append({"name": fn.get("name"), "arguments_raw": json.dumps(args, ensure_ascii=False),
                        "arguments": args, "parse_ok": True})
        else:
            try:
                parsed = json.loads(args) if args else {}
                ok = isinstance(parsed, dict)
            except (TypeError, json.JSONDecodeError):
                parsed, ok = None, False
            out.append({"name": fn.get("name"), "arguments_raw": args,
                        "arguments": parsed if ok else None, "parse_ok": ok})
    return out


class Ollama:
    """Ollama native /api/chat. `think: false` disables Qwen thinking mode."""

    def __init__(self, model, base_url="http://localhost:11434", seed=42, think_param=True):
        self.model, self.base, self.seed, self.think_param = model, base_url.rstrip("/"), seed, think_param

    def chat(self, messages, tools):
        payload = {"model": self.model, "messages": messages, "stream": False,
                   "tools": [{"type": "function", "function": t} for t in tools],
                   "options": {"temperature": 0, "seed": self.seed}}
        if self.think_param:
            payload["think"] = False
        r = _post(f"{self.base}/api/chat", payload)
        m = r.get("message", {})
        return {"content": m.get("content", ""), "tool_calls": _norm_calls(m.get("tool_calls")),
                "thinking": m.get("thinking"), "eval_count": r.get("eval_count"),
                "prompt_eval_count": r.get("prompt_eval_count")}


class OpenAICompatible:
    """Any OpenAI-compatible /chat/completions endpoint (hosted baseline)."""

    def __init__(self, model, base_url, api_key_env="OPENAI_API_KEY", seed=42):
        self.model, self.base, self.seed = model, base_url.rstrip("/"), seed
        self.key = os.environ.get(api_key_env)
        if not self.key:
            raise SystemExit(f"set {api_key_env}")

    def chat(self, messages, tools):
        payload = {"model": self.model, "messages": messages, "temperature": 0, "seed": self.seed,
                   "tools": [{"type": "function", "function": t} for t in tools]}
        r = _post(f"{self.base}/chat/completions", payload, {"Authorization": f"Bearer {self.key}"})
        m = r["choices"][0]["message"]
        u = r.get("usage", {})
        return {"content": m.get("content") or "", "tool_calls": _norm_calls(m.get("tool_calls")),
                "thinking": None, "eval_count": u.get("completion_tokens"),
                "prompt_eval_count": u.get("prompt_tokens")}


class Anthropic:
    """Anthropic Messages API (hosted baseline option)."""

    def __init__(self, model, base_url="https://api.anthropic.com", api_key_env="ANTHROPIC_API_KEY", seed=42):
        self.model, self.base = model, base_url.rstrip("/")
        self.key = os.environ.get(api_key_env)
        if not self.key:
            raise SystemExit(f"set {api_key_env}")

    def chat(self, messages, tools):
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        conv = [m for m in messages if m["role"] != "system"]
        # The API requires the first turn to be the user's; the agent opener starts the call.
        if conv and conv[0]["role"] == "assistant":
            conv = [{"role": "user", "content": "(call connected)"}] + conv
        payload = {"model": self.model, "max_tokens": 512, "temperature": 0, "system": system,
                   "messages": conv,
                   "tools": [{"name": t["name"], "description": t["description"],
                              "input_schema": t["parameters"]} for t in tools]}
        r = _post(f"{self.base}/v1/messages", payload,
                  {"x-api-key": self.key, "anthropic-version": "2023-06-01"})
        text = "".join(b.get("text", "") for b in r["content"] if b["type"] == "text")
        calls = [{"name": b["name"], "arguments": b["input"]} for b in r["content"] if b["type"] == "tool_use"]
        u = r.get("usage", {})
        return {"content": text, "tool_calls": _norm_calls(calls), "thinking": None,
                "eval_count": u.get("output_tokens"), "prompt_eval_count": u.get("input_tokens")}


class Mock:
    """Gold-echoing backend with injected errors — tests the pipeline without a model."""

    def __init__(self, model="mock", **_):
        self.model = model
        self._cases = {}

    def bind(self, cases):
        self._cases = {c["borrower_turn"]: c for c in cases}

    def chat(self, messages, tools):
        c = self._cases[messages[-1]["content"]]
        gold = c["accept"][0]
        h = sum(map(ord, c["id"])) % 10
        if gold is None:
            calls = [] if h else [{"name": "log_disposition", "arguments": {"code": "CALLBACK"}}]
        else:
            args = {k: v[0] for k, v in gold["args"].items()}
            if h == 1 and c["lang"] != "en":
                calls = []                                   # missed
            elif h == 2 and "promised_amount" in args:
                args["promised_amount"] = str(args["promised_amount"])  # malformed type
                calls = [{"name": gold["tool"], "arguments": args}]
            elif h == 3 and "promised_date" in args:
                args["promised_date"] = "2026-10-09"         # wrong date
                calls = [{"name": gold["tool"], "arguments": args}]
            else:
                calls = [{"name": gold["tool"], "arguments": args}]
        return {"content": "", "tool_calls": _norm_calls(calls), "thinking": None,
                "eval_count": 0, "prompt_eval_count": 0}


def make_backend(args):
    if args.backend == "ollama":
        return Ollama(args.model, args.base_url or "http://localhost:11434", args.seed,
                      think_param=not args.no_think_param)
    if args.backend == "openai":
        return OpenAICompatible(args.model, args.base_url or "https://api.openai.com/v1",
                                args.api_key_env or "OPENAI_API_KEY", args.seed)
    if args.backend == "anthropic":
        return Anthropic(args.model, args.base_url or "https://api.anthropic.com",
                         args.api_key_env or "ANTHROPIC_API_KEY")
    if args.backend == "mock":
        return Mock(args.model)
    raise SystemExit(f"unknown backend {args.backend}")


def add_backend_args(ap):
    ap.add_argument("--backend", required=True, choices=["ollama", "openai", "anthropic", "mock"])
    ap.add_argument("--model", required=True)
    ap.add_argument("--base-url")
    ap.add_argument("--api-key-env")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-think-param", action="store_true",
                    help="omit Ollama's think:false (only for models without a thinking mode)")


def call_with_retry(backend, messages, tools, tries=3):
    for i in range(tries):
        try:
            t0 = time.time()
            r = backend.chat(messages, tools)
            r["latency_s"] = round(time.time() - t0, 3)
            r["error"] = None
            return r
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as e:
            err = f"{type(e).__name__}: {getattr(e, 'read', lambda: b'')().decode(errors='ignore')[:300] or e}"
            if i == tries - 1:
                return {"content": "", "tool_calls": [], "error": err, "latency_s": None}
            time.sleep(2 ** i)
