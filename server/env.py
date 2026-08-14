"""Environment detection: running ComfyUI instance, models on disk, Ollama."""

import json
import os
import urllib.request
import urllib.error

from . import config

COMFY_DEFAULT_PORT = 8188
MODEL_DIRS = ["checkpoints", "diffusion_models", "text_encoders", "vae", "loras", "clip", "unet", "clip_vision", "style_models"]

# Model filename -> combos key we read from /object_info, and which folder they live in.
MODEL_COMBO_NODES = {
    "UNETLoader": ("unet_name", "diffusion_models"),
    "CLIPLoader": ("clip_name", "text_encoders"),
    "VAELoader": ("vae_name", "vae"),
    "CheckpointLoaderSimple": ("ckpt_name", "checkpoints"),
    "LoraLoader": ("model_name", "loras"),
    "LoraLoaderModelOnly": ("model_name", "loras"),
}


def _http_json(url, timeout=6):
    req = urllib.request.Request(url, headers={"User-Agent": "total-director/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def comfy_base():
    return config.get()["llm"].get("comfy_host") or f"http://127.0.0.1:{COMFY_DEFAULT_PORT}"


def query_system_stats():
    try:
        return _http_json(f"{comfy_base()}/system_stats", timeout=4)
    except Exception:
        return None


def query_object_info(node_names=None):
    try:
        if node_names:
            info = {}
            for n in node_names:
                try:
                    info[n] = _http_json(f"{comfy_base()}/object_info/{n}", timeout=4)[n]
                except Exception:
                    pass
            return info or None
        return _http_json(f"{comfy_base()}/object_info", timeout=8)
    except Exception:
        return None


def _extract_combo(obj):
    """Extract the list of options from an object_info field definition."""
    if not obj or not isinstance(obj, list):
        return []
    if isinstance(obj[0], list):
        return [str(x) for x in obj[0]]
    if isinstance(obj[1], dict):
        opts = obj[1].get("Options") or obj[1].get("options")
        if opts:
            return [str(x) for x in opts]
    return []


def get_node_classes():
    info = query_object_info()
    if info:
        return sorted(info.keys())
    return None


def _models_from_info(info):
    result = {d: [] for d in MODEL_DIRS}
    if not info:
        return result
    for node, (field, folder) in MODEL_COMBO_NODES.items():
        node_def = info.get(node)
        if not node_def:
            continue
        try:
            field_def = node_def["input"]["required"].get(field)
        except Exception:
            field_def = None
        options = _extract_combo(field_def)
        if options:
            result[folder] = options
    return result


def _find_comfy_models_dir():
    """Try to resolve the models directory. Best: ComfyUI's folder_paths module."""
    try:
        import folder_paths  # type: ignore

        base = folder_paths.models_dir
        if base:
            return str(base)
    except Exception:
        pass
    return None


def models_from_disk(models_dir=None):
    models_dir = models_dir or _find_comfy_models_dir()
    result = {d: [] for d in MODEL_DIRS}
    if not models_dir or not os.path.isdir(models_dir):
        return result
    for folder in MODEL_DIRS:
        base = os.path.join(models_dir, folder)
        if not os.path.isdir(base):
            continue
        for root, _dirs, files in os.walk(base):
            for fn in sorted(files):
                if fn.lower().endswith((".safetensors", ".ckpt", ".pt", ".pth", ".bin")):
                    rel = os.path.relpath(os.path.join(root, fn), base)
                    result[folder].append(rel.replace("\\", "/"))
    return result


def merge_models(object_info_models, disk_models):
    merged = {}
    for folder in MODEL_DIRS:
        entries = list(object_info_models.get(folder) or [])
        seen = set(entries)
        for m in disk_models.get(folder) or []:
            if m not in seen:
                entries.append(m)
                seen.add(m)
        merged[folder] = entries
    return merged


def check_ollama(host):
    try:
        data = _http_json(f"{host}/api/tags", timeout=4)
        names = [m.get("name") for m in data.get("models", []) if m.get("name")]
        return {"running": True, "models": sorted(names)}
    except Exception:
        return {"running": False, "models": []}


def query_history_entry(prompt_id):
    """Fetch one history entry from ComfyUI /history/{prompt_id}."""
    try:
        data = _http_json(f"{comfy_base()}/history/{prompt_id}", timeout=6)
    except Exception:
        return None
    return (data or {}).get(prompt_id)


def pipeline_availability(models, nodes):
    h3_node = "MiniMaxH3ImageToVideo" in nodes
    ref_node = "MiniMaxH3ReferenceToVideo" in nodes
    fl2va = any("fl2va" in m.lower() for m in models["diffusion_models"])
    ref2va = any("ref2va" in m.lower() for m in models["diffusion_models"])
    sdxl = any(m for m in models["checkpoints"])
    clip_qwen = any(m for m in models["text_encoders"])

    def ok(cond, reason=""):
        return {"available": bool(cond), "reason": "" if cond else reason}

    return {
        "t2v": ok(h3_node and fl2va and clip_qwen,
                  "缺少 MiniMaxH3ImageToVideo 节点或 fl2va 扩散模型 / qwen 文本编码器"),
        "i2v": ok(h3_node and fl2va and clip_qwen,
                  "缺少 MiniMaxH3ImageToVideo 节点或 fl2va 扩散模型"),
        "r2v": ok(ref_node and ref2va,
                  "缺少 MiniMaxH3ReferenceToVideo 节点或 ref2va 扩散模型 minimax_h3_ref2va_pruned_int8_convrot.safetensors"),
        "sdxl2v": ok(h3_node and fl2va and sdxl and clip_qwen,
                     "需要 MiniMax H3 + SDXL checkpoint 才能走 首帧图→视频 全流程"),
    }


def snapshot(models_dir=None):
    """Build the full environment snapshot for the frontend panel and the LLM context."""
    stats = query_system_stats()
    info = query_object_info()
    nodes = sorted(info.keys()) if info else (get_node_classes() or [])

    obj_models = _models_from_info(info)
    disk_models = models_from_disk(models_dir)
    models = merge_models(obj_models, disk_models)

    gpu = []
    if stats:
        for d in stats.get("devices", []):
            vram_total = d.get("vram_total_bytes") or d.get("vram_total") or 0
            vram_free = d.get("vram_free_bytes") or d.get("vram_free") or 0
            gpu.append({
                "name": d.get("name"),
                "type": d.get("type"),
                "vram_total_gb": round(vram_total / 1024 ** 3, 2),
                "vram_free_gb": round(vram_free / 1024 ** 3, 2),
            })

    ollama_host = config.get()["llm"].get("ollama_host") or "http://127.0.0.1:11434"
    ollama = check_ollama(ollama_host)

    comfy = {"running": False, "version": None, "port": COMFY_DEFAULT_PORT, "frontend": None}
    if stats:
        sysinfo = stats.get("system", {})
        comfy.update({
            "running": True,
            "version": sysinfo.get("comfyui_version"),
            "frontend": sysinfo.get("required_frontend_version"),
            "os": sysinfo.get("os"),
            "ram_total_gb": round((sysinfo.get("ram_total_bytes") or sysinfo.get("ram_total") or 0) / 1024 ** 3, 1),
            "ram_free_gb": round((sysinfo.get("ram_free_bytes") or sysinfo.get("ram_free") or 0) / 1024 ** 3, 1),
        })

    return {
        "comfy": comfy,
        "gpu": gpu,
        "models": models,
        "nodes": nodes,
        "pipelines": pipeline_availability(models, set(nodes)),
        "ollama": ollama,
        "has_key_nodes": {
            "MiniMaxH3ImageToVideo": "MiniMaxH3ImageToVideo" in nodes,
            "MiniMaxH3ReferenceToVideo": "MiniMaxH3ReferenceToVideo" in nodes,
            "MiniMaxH3SpeedCache": "MiniMaxH3SpeedCache" in nodes,
        },
    }
