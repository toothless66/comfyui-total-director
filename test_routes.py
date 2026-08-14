"""Standalone aiohttp route test for the Total Director backend.

Mocks the ComfyUI integrations (llm/env) so the whole handler stack can be
exercised without restarting the running ComfyUI instance.

Usage:
  <comfyui_python> test_routes.py
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from server import routes


class FakePlan:
    def __init__(self):
        self.calls = 0

    async def plan(self, message, snap, images=None):
        self.calls += 1
        return {
            "pipeline": "t2v", "summary_cn": "测试视频", "duration_s": 5.0,
            "aspect": "16:9", "aspect_label": "16:9 (Widescreen)", "megapixels": 0.4,
            "sampler": "res_multistep", "steps": 20, "seed": 123,
            "audio": "amb", "notes_cn": "ok", "keyframe_prompt": "",
            "keyframe_negative": "", "megaprompt": "A test prompt.",
            "_meta": {"provider": "fake", "model": "fake"},
        }

    async def refine_plan(self, prev, instruction, snap):
        return await self.plan(instruction, snap)


class FakeWorkflow:
    def build(self, plan, env=None, cfg=None, first_frame_image=None, reference_images=None):
        return {"nodes": [{"id": 1, "type": "Fake"}], "links": [], "last_node_id": 1}

    def compute_dimensions(self, aspect, mp):
        return 832, 480

    def frame_length(self, duration_s):
        return int(round(duration_s * 24))


async def main():
    from server import config, env, llm, workflow

    routes.llm = FakePlan()
    routes.workflow = FakeWorkflow()
    routes.env.snapshot = lambda: {
        "comfy": {"running": True, "version": "0.30.0"},
        "gpu": [], "models": {}, "nodes": ["MiniMaxH3ImageToVideo"],
        "pipelines": {
            "t2v": {"available": True, "reason": ""},
            "i2v": {"available": True, "reason": ""},
            "r2v": {"available": True, "reason": ""},
            "sdxl2v": {"available": True, "reason": ""},
        },
    }
    routes.env.query_history_entry = lambda prompt_id: (
        {
            "status": {"status": "success"},
            "outputs": {"9": {"images": [{"filename": "shot.webm", "subfolder": "", "type": "output"}]}},
        }
        if prompt_id == "abc123"
        else None
    )

    rt = web.RouteTableDef()
    routes.register(rt)

    app = web.Application()
    app.add_routes(rt)
    client = TestClient(TestServer(app))

    async def check(method, path, payload=None, expect=200):
        kw = {}
        if payload is not None:
            kw["json"] = payload
        resp = await client.request(method, path, **kw)
        body = await resp.json()
        tag = "OK" if resp.status == expect else "FAIL"
        print(f"[{tag}] {method} {path} -> {resp.status}: ok={body.get('ok')}")
        if body.get("error"):
            print(f"        error={body['error']}")
        if resp.status != expect:
            print(f"        body={json.dumps(body, ensure_ascii=False)[:300]}")
            sys.exit(1)

    await client.start_server()
    try:
        await check("GET", "/director/status")
        await check("GET", "/director/config")
        await check("GET", "/director/models")
        await check("POST", "/director/plan", {"message": "test"}, expect=200)
        await check("POST", "/director/plan", {}, expect=400)  # empty message
        await check("POST", "/director/refine", {}, expect=400)  # missing plan
        await check("POST", "/director/build", {}, expect=400)  # missing plan
        await check("POST", "/director/build", {"plan": {"pipeline": "t2v"}})
        await check("POST", "/director/config", {"config": {"llm": {"api_key": "sekret"}}})
        await check("POST", "/director/config", {"config": {"llm": {"api_key": "******"}}})
        await check("GET", "/director/result/abc123", expect=200)
        await check("GET", "/director/result/nonexistent", expect=200)
    finally:
        await client.close()
    print("\nAll route tests passed.")


if __name__ == "__main__":
    asyncio.run(main())