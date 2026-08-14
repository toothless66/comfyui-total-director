"""Configuration management for the Total Director extension."""

import json
import os
import threading

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")

_DEFAULTS = {
    "llm": {
        "provider": "ollama",  # "ollama" | "api"
        "ollama_host": "http://127.0.0.1:11434",
        "ollama_model": "qwen3-vl:8b",
        "api_base": "https://api.deepseek.com/v1",
        "api_key": "",
        "api_model": "deepseek-chat",
        "vision_enabled": True,
        "temperature": 0.6,
        "roles_mode": "single",  # "single" | "dual" — dual coordinates two local models
        "stage_a_model": "deepseek-r1:14b",  # dual: 梳理需求 -> 生产参数 (planner)
        "stage_b_model": "deepseek-r1:14b",  # dual: 写提示词 megaprompt (writer)
        "stage_c_model": "qwen3-vl:8b",      # dual: 操作实现/终审 (executor, 视觉)
    },
    "build": {
        "default_aspect": "16:9",
        "default_megapixels": 0.4,
        "max_duration_s": 15.0,
        "min_duration_s": 1.0,
        "sampler": "res_multistep",
        "steps": 20,
        "sdxl_checkpoint": "RealVisXL_V5.0_fp16.safetensors",
        "sdxl_negative": "text, watermark, signature, logo, lowres, blurry, jpeg artifacts, deformed, bad anatomy",
        "sdxl_steps": 28,
        "sdxl_cfg": 7.0,
        "sdxl_sampler": "euler",
        "sdxl_scheduler": "normal",
        "output_prefix": "video/Director",
        "keyframe_prefix": "director/keyframes",
    },
}

_lock = threading.Lock()
_cfg = None


def _deep_merge(base, override):
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            out[k] = _deep_merge(base[k], v)
        else:
            out[k] = v
    return out


def load():
    """Load config, merging saved values over defaults. Returns a fresh copy."""
    global _cfg
    with _lock:
        cfg = json.loads(json.dumps(_DEFAULTS))
        if os.path.exists(_CONFIG_PATH):
            try:
                with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                cfg = _deep_merge(cfg, saved)
            except Exception:
                pass
        _cfg = cfg
        return json.loads(json.dumps(cfg))


def get():
    if _cfg is None:
        return load()
    with _lock:
        return json.loads(json.dumps(_cfg))


def save(patch):
    """Merge a patch dict into config and persist. Returns full new config."""
    with _lock:
        cfg = json.loads(json.dumps(_DEFAULTS))
        if os.path.exists(_CONFIG_PATH):
            try:
                with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = _deep_merge(cfg, json.load(f))
            except Exception:
                pass
        cfg = _deep_merge(cfg, patch)
        try:
            with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        global _cfg
        _cfg = cfg
        return json.loads(json.dumps(cfg))


def config_path():
    return _CONFIG_PATH
