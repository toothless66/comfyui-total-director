"""Standalone smoke test for the Total Director backend (runs outside ComfyUI).

Usage:
  python -m test_standalone env
  python -m test_standalone build
  python -m test_standalone plan "<brief>"
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import config, env, llm, workflow  # noqa: E402

MODELS_DIR = r"D:\MiniMaxH3\ComfyUI_windows_portable\ComfyUI\models"


def test_env():
    snap = env.snapshot(models_dir=MODELS_DIR)
    print("== comfy ==", json.dumps(snap["comfy"], ensure_ascii=False))
    print("== gpu ==", json.dumps(snap["gpu"], ensure_ascii=False))
    print("== pipelines ==", json.dumps(snap["pipelines"], ensure_ascii=False))
    print("== ollama ==", json.dumps(snap["ollama"], ensure_ascii=False))
    for folder, items in snap["models"].items():
        if items:
            print(f"== models[{folder}] ==", items[:6])
    return snap


def test_build(snap):
    cfg = config.get()
    raw = {
        "pipeline": "sdxl2v", "summary_cn": "测试",
        "megaprompt": "A cinematic slow push-in on a rusty robot head, dust motes, amber rim light, shallow DOF.\n\n[0s-2s] slow dolly in.\n\nAudio: low hum, ticking servos.",
        "duration_s": 5, "aspect": "16:9", "megapixels": 0.4,
        "sampler": "res_multistep", "steps": 20, "seed": 0,
        "keyframe_prompt": "close-up of a rusty robot head, dramatic amber-cyan lighting, dust motes, photorealistic, 35mm",
        "keyframe_negative": "text, watermark, lowres, blurry",
        "audio": "low hum", "notes_cn": "ok",
    }
    plan = llm.normalize_plan(raw, snap, cfg)
    plan["megaprompt"] = raw["megaprompt"]
    for pipe, first_frame, refs in [
        ("t2v", None, None),
        ("i2v", "input/test_first.png", None),
        ("r2v", None, ["ref1.png", "ref2.png"]),
        ("sdxl2v", None, None),
    ]:
        p = dict(plan); p["pipeline"] = pipe
        wf = workflow.build(p, env=snap, cfg=cfg, first_frame_image=first_frame, reference_images=refs)
        print(f"\n== build {pipe}: nodes={len(wf['nodes'])} links={len(wf['links'])} "
              f"last_node={wf.get('last_node_id')} last_link={wf.get('last_link_id')}")
        inst = [n for n in wf["nodes"] if n["type"] in {(s or {}).get("id") for s in (wf.get("definitions") or {}).get("subgraphs", [])}]
        if inst:
            print(f"   instance widgets[0..4] = {[str(x)[:40] for x in inst[0]['widgets_values'][:5]]}")
        sel = [n for n in wf["nodes"] if n.get("type") == "ResolutionSelector"]
        if sel:
            print("   ResolutionSelector =", sel[0]["widgets_values"])
        if pipe == "sdxl2v":
            types = [n["type"] for n in wf["nodes"]]
            print("   sdxl section types:", [t for t in types if t in ("CheckpointLoaderSimple", "KSampler", "EmptyLatentImage", "CLIPTextEncode", "VAEDecode", "SaveImage")])
        if pipe == "i2v":
            load = [n for n in wf["nodes"] if n.get("type") == "LoadImage"]
            print("   LoadImage =", load[0]["widgets_values"] if load else None)
        if pipe == "r2v":
            load = [n for n in wf["nodes"] if n.get("type") == "LoadImage"]
            print("   LoadImage(s) =", [n["widgets_values"] for n in load])
            ref = [n for n in wf["nodes"] if n.get("type") == "MiniMaxH3ReferenceToVideo"]
            if ref:
                print("   RefToVideo widgets =", ref[0]["widgets_values"])
    return plan


def test_plan(snap, brief):
    async def _go():
        plan = await llm.plan(brief, snap)
        print("== plan ==")
        print(json.dumps({k: v for k, v in plan.items() if k != "_meta"}, ensure_ascii=False, indent=2)[:1800])
        print("== meta ==", plan.get("_meta"))
    asyncio.run(_go())


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "env"
    snap = test_env()
    if mode == "build":
        test_build(snap)
    elif mode == "plan":
        brief = sys.argv[2] if len(sys.argv) > 2 else "生成一段5秒的科幻城市夜景预告片,16:9"
        test_plan(snap, brief)