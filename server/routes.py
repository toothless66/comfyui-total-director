"""aiohttp endpoints for the Total Director panel.

Registered onto ComfyUI's PromptServer routes table by the package __init__.
"""

import asyncio
import json
import urllib.parse

from aiohttp import web

from . import config, env, llm, workflow


def _bad(message, status=400):
    return web.json_response({"ok": False, "error": message}, status=status)


def _ok(**data):
    return web.json_response({"ok": True, **data})


async def _read_json(request):
    try:
        return await request.json()
    except Exception:
        return {}


def _masked_config(cfg):
    out = json.loads(json.dumps(cfg))
    if out["llm"].get("api_key"):
        out["llm"]["api_key"] = "******"
    return out


def _plan_preview(plan):
    """Human-facing plan preview with computed geometry."""
    w, h = workflow.compute_dimensions(plan["aspect"], plan["megapixels"])
    return {
        "pipeline": plan["pipeline"],
        "summary_cn": plan["summary_cn"],
        "duration_s": plan["duration_s"],
        "frames": workflow.frame_length(plan["duration_s"]),
        "aspect": plan["aspect"],
        "aspect_label": plan["aspect_label"],
        "megapixels": plan["megapixels"],
        "width": w,
        "height": h,
        "sampler": plan["sampler"],
        "steps": plan["steps"],
        "seed": plan["seed"],
        "audio": plan["audio"],
        "notes_cn": plan["notes_cn"],
        "megaprompt_preview": plan["megaprompt"][:400],
        "roles": (plan.get("_meta") or {}).get("roles") or None,
    }


async def _snapshot():
    # env.snapshot() does blocking urllib calls to *our own* HTTP server
    # (/system_stats, /object_info). Run it off-thread so the aiohttp event
    # loop is free to answer those self-requests (otherwise it deadlocks).
    return await asyncio.to_thread(env.snapshot)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def handle_status(request):
    snap = await _snapshot()
    cfg = config.get()
    snap["llm"] = {
        "provider": cfg["llm"].get("provider"),
        "ollama_host": cfg["llm"].get("ollama_host"),
        "ollama_model": cfg["llm"].get("ollama_model"),
        "api_model": cfg["llm"].get("api_model"),
        "api_key_set": bool(cfg["llm"].get("api_key")),
        "vision_enabled": bool(cfg["llm"].get("vision_enabled", True)),
        "api_base": cfg["llm"].get("api_base"),
    }
    snap["build"] = cfg.get("build", {})
    return _ok(env=snap)


async def handle_plan(request):
    body = await _read_json(request)
    message = (body.get("message") or "").strip()
    if not message:
        return _bad("缺少需求描述或分镜脚本")

    snap = await _snapshot()
    image_b64 = body.get("image_base64")
    images = [image_b64] if image_b64 else None

    try:
        plan = await llm.plan(message, snap, images=images)
    except llm.LLMError as e:
        return _bad(f"规划失败: {e}", status=502)

    return _ok(plan=plan, preview=_plan_preview(plan), model=plan.get("_meta"))


async def handle_refine(request):
    body = await _read_json(request)
    prev = body.get("plan")
    instruction = (body.get("instruction") or "").strip()
    if not prev or not instruction:
        return _bad("缺少 plan 或调整指令")

    snap = await _snapshot()
    try:
        plan = await llm.refine_plan(prev, instruction, snap)
    except llm.LLMError as e:
        return _bad(f"调整失败: {e}", status=502)

    return _ok(plan=plan, preview=_plan_preview(plan), model=plan.get("_meta"))


async def handle_build(request):
    body = await _read_json(request)
    plan = body.get("plan")
    if not plan:
        return _bad("缺少 plan")

    snap = await _snapshot()
    pipeline = (plan.get("pipeline") or "t2v").strip()
    pipe = snap.get("pipelines", {}).get(pipeline, {})
    if not pipe.get("available"):
        return _bad(pipe.get("reason") or f"流水线 {pipeline} 当前不可用")

    try:
        wf = workflow.build(
            plan,
            env=snap,
            cfg=config.get(),
            first_frame_image=body.get("first_frame_image"),
            reference_images=body.get("reference_images") or [],
        )
    except workflow.BuildError as e:
        return _bad(str(e))

    return _ok(workflow=wf, workflow_json=json.dumps(wf, ensure_ascii=False),
               name=body.get("name") or f"Director_{pipeline}")


async def handle_get_config(request):
    return _ok(config=_masked_config(config.get()))


async def handle_set_config(request):
    body = await _read_json(request)
    patch = body.get("config")
    if not isinstance(patch, dict):
        return _bad("缺少 config")
    if "api_key" in patch and patch["api_key"] == "******":
        # unchanged sentinel: keep the existing key
        current = config.get()
        patch["api_key"] = current["llm"].get("api_key", "")
    try:
        new_cfg = config.save(patch)
    except Exception as e:
        return _bad(f"保存配置失败: {e}")
    return _ok(config=_masked_config(new_cfg))


async def handle_models(request):
    snap = await _snapshot()
    return _ok(
        models=snap.get("models", {}),
        pipelines=snap.get("pipelines", {}),
        gpu=snap.get("gpu", []),
    )


def _output_files(history_entry):
    """Collect {filename, subfolder, type} entries from a history entry's outputs."""
    files = []
    outputs = (history_entry or {}).get("outputs") or {}
    for node_out in outputs.values():
        for key in ("images", "gifs", "videos", "audio", "files"):
            for item in (node_out.get(key) or []):
                if isinstance(item, dict) and item.get("filename"):
                    files.append({
                        "filename": item["filename"],
                        "subfolder": item.get("subfolder") or "",
                        "type": item.get("type") or "output",
                    })
    return files


async def handle_result(request):
    """Return output files produced by a finished prompt_id.

    Look up ComfyUI /history/{prompt_id}, extract SaveImage/SaveVideo outputs and
    expose them as viewable URLs (/view?...). Frontend calls this after an
    execution_success event to recover the finished video into the panel.
    """
    prompt_id = (request.match_info.get("prompt_id") or "").strip()
    if not prompt_id:
        return _bad("缺少 prompt_id")

    try:
        entry = await asyncio.to_thread(env.query_history_entry, prompt_id)
    except Exception as e:
        return _bad(f"查询历史失败: {e}", status=502)

    if entry is None:
        return _ok(found=False, files=[])

    status = (entry.get("status") or {})
    files = _output_files(entry)
    out = []
    for f in files:
        q = "filename=%s" % urllib.parse.quote(f["filename"])
        if f.get("subfolder"):
            q += "&subfolder=%s" % urllib.parse.quote(f["subfolder"])
        q += "&type=%s" % urllib.parse.quote(f.get("type") or "output")
        f["url"] = f"/view?{q}"
        out.append(f)
    return _ok(found=True, status=status.get("status"), files=out)


def register(routes):
    """Register handlers onto an aiohttp RouteTableDef (decorator-call syntax)."""
    routes.get("/director/status")(handle_status)
    routes.post("/director/plan")(handle_plan)
    routes.post("/director/refine")(handle_refine)
    routes.post("/director/build")(handle_build)
    routes.get("/director/config")(handle_get_config)
    routes.post("/director/config")(handle_set_config)
    routes.get("/director/models")(handle_models)
    routes.get("/director/result/{prompt_id}")(handle_result)
