"""Workflow assembly: build save-format ComfyUI workflows from a Director Plan.

Templates are the user's own working MiniMax H3 workflows (h3_t2v / h3_i2v / h3_r2v),
so structure, subgraph definitions and node wiring are guaranteed valid for this
ComfyUI version. We only patch known widget slots and add links for the combined
SDXL-first-frame pipeline.
"""

import json
import os

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

ASPECT_RATIOS = {
    "1:1": (1, 1), "16:9": (16, 9), "9:16": (9, 16), "4:3": (4, 3),
    "3:2": (3, 2), "2:3": (2, 3), "3:4": (3, 4), "21:9": (21, 9),
}


class BuildError(Exception):
    pass


def frame_length(duration_s):
    """Snap seconds at 24fps to the model's 17k+5 frame grid."""
    n = max(5, round(float(duration_s) * 24))
    return n + (5 - (n % 17)) % 17


def compute_dimensions(aspect_key, megapixels):
    aw, ah = ASPECT_RATIOS.get(aspect_key, (16, 9))
    h = round((megapixels * 1e6 * ah / aw) ** 0.5)
    w = round((megapixels * 1e6 * aw / ah) ** 0.5)
    h = max(32, round(h / 32) * 32)
    w = max(32, round(w / 32) * 32)
    # MiniMax H3 native canvas: short edge capped at 768px
    if min(w, h) > 768:
        scale = 768.0 / min(w, h)
        w = max(32, round(w * scale / 32) * 32)
        h = max(32, round(h * scale / 32) * 32)
    return w, h


def _load_template(name):
    path = os.path.join(TEMPLATE_DIR, name)
    if not os.path.exists(path):
        raise BuildError(f"模板缺失: {name}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _find(nodes, node_type=None, node_id=None, order=None):
    matches = [n for n in nodes
               if (node_type is None or n.get("type") == node_type)
               and (node_id is None or n.get("id") == node_id)]
    if order == "asc":
        matches.sort(key=lambda n: n.get("id", 0))
    elif order == "desc":
        matches.sort(key=lambda n: n.get("id", 0), reverse=True)
    return matches


def _set_widget(node, idx, value):
    if not node or not isinstance(node.get("widgets_values"), list):
        raise BuildError(f"节点 {node.get('type')} 没有 widgets_values")
    wv = node["widgets_values"]
    while len(wv) <= idx:
        wv.append(None)
    wv[idx] = value


def _find_subgraph_instance(nodes, subgraphs):
    sub_ids = {s.get("id") for s in (subgraphs or [])}
    for n in nodes:
        if n.get("type") in sub_ids:
            return n
    return None


# ---------------------------------------------------------------------------
# Patch helpers for the shared H3 subgraph pipeline (t2v / i2v)
# ---------------------------------------------------------------------------

def _patch_h3_subgraph(wf, plan):
    nodes = wf.get("nodes", [])
    subgraphs = (wf.get("definitions") or {}).get("subgraphs", [])

    inst = _find_subgraph_instance(nodes, subgraphs)
    if inst is None:
        raise BuildError("模板中未找到 MiniMax H3 子图实例")

    # instance widget slots: [0]=prompt [1]=width [2]=height [3]=duration [4]=seed [5..8]=models
    _set_widget(inst, 0, plan["megaprompt"])
    _set_widget(inst, 1, plan["_width"])
    _set_widget(inst, 2, plan["_height"])
    _set_widget(inst, 3, plan["duration_s"])
    _set_widget(inst, 4, plan["seed"])

    # ResolutionSelector controls width/height via links
    sel = _find(nodes, node_type="ResolutionSelector")
    if sel:
        sel[0]["widgets_values"] = [plan["aspect_label"], plan["megapixels"], 32]

    return inst


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def build_t2v(plan, env=None, cfg=None):
    wf = _load_template("h3_t2v.json")
    _patch_h3_subgraph(wf, plan)
    return wf


def build_i2v(plan, env=None, cfg=None, first_frame_image=None):
    wf = _load_template("h3_i2v.json")
    _patch_h3_subgraph(wf, plan)
    if first_frame_image:
        # the LoadImage feeding the subgraph instance's first_frame input
        inst = _find_subgraph_instance(wf.get("nodes", []),
                                       (wf.get("definitions") or {}).get("subgraphs", []))
        loaders = _find(wf.get("nodes", []), node_type="LoadImage", order="asc")
        if not loaders:
            raise BuildError("i2v 模板中没有 LoadImage 节点")
        _set_widget(loaders[0], 0, first_frame_image)
    return wf


def build_r2v(plan, env=None, cfg=None, reference_images=None):
    wf = _load_template("h3_r2v.json")
    nodes = wf.get("nodes", [])

    match = _find(nodes, node_type="MiniMaxH3ReferenceToVideo")
    if not match:
        raise BuildError("r2v 模板中没有 MiniMaxH3ReferenceToVideo 节点")
    node = match[0]
    # widgets: [prompt, width, height, length, ref_image_size]
    _set_widget(node, 1, plan["_width"])
    _set_widget(node, 2, plan["_height"])
    _set_widget(node, 3, frame_length(plan["duration_s"]))
    _set_widget(node, 4, "match")

    prompt_node = _find(nodes, node_type="PrimitiveStringMultiline")
    if prompt_node:
        _set_widget(prompt_node[0], 0, plan["megaprompt"])

    sel = _find(nodes, node_type="ResolutionSelector")
    if sel:
        sel[0]["widgets_values"] = [plan["aspect_label"], plan["megapixels"], 32]

    dur = _find(nodes, node_type="PrimitiveFloat")
    if dur:
        _set_widget(dur[0], 0, plan["duration_s"])

    loaders = _find(nodes, node_type="LoadImage", order="asc")
    refs = reference_images or []
    for i, loader in enumerate(loaders[:2]):
        if i < len(refs) and refs[i]:
            _set_widget(loader, 0, refs[i])

    return wf


def build_sdxl2v(plan, env=None, cfg=None):
    """SDXL first-frame -> MiniMax H3 I2V, all in one graph."""
    wf = _load_template("h3_t2v.json")
    inst = _patch_h3_subgraph(wf, plan)

    build = (cfg or {}).get("build", {})
    ckpt = build.get("sdxl_checkpoint")
    if ckpt and env:
        models = env.get("models", {})
        checkpoints = models.get("checkpoints") or []
        if checkpoints and ckpt not in checkpoints:
            ckpt = checkpoints[0]
    elif env and (env.get("models", {}).get("checkpoints") or []):
        ckpt = env["models"]["checkpoints"][0]
    if not ckpt:
        raise BuildError("没有可用的 SDXL checkpoint 用于首帧生成")

    sel = _find(wf.get("nodes", []), node_type="ResolutionSelector")
    sel = sel[0] if sel else None

    next_id = max(n.get("id", 0) for n in wf.get("nodes", [])) + 1
    last_link = max((l[0] for l in wf.get("links", [])), default=0) + 1

    new_id = {"ckpt": next_id, "pos": next_id + 1, "neg": next_id + 2,
              "latent": next_id + 3, "ksampler": next_id + 4,
              "vae_decode": next_id + 5, "save": next_id + 6}

    inst_first_frame_slot = None
    for i, inp in enumerate(inst.get("inputs", [])):
        if inp.get("name") == "first_frame":
            inst_first_frame_slot = i
            break
    if inst_first_frame_slot is None:
        raise BuildError("子图实例缺少 first_frame 输入")

    def new_link(origin_id, origin_slot, target_id, target_slot, ltype):
        nonlocal last_link
        last_link += 1
        wf["links"].append([last_link, origin_id, origin_slot, target_id, target_slot, ltype])
        return last_link

    def widget_input(name, wtype, link=None):
        d = {"name": name, "type": wtype, "widget": {"name": name}}
        if link is not None:
            d["link"] = link
        return d

    # --- CheckpointLoaderSimple ---
    wf["nodes"].append({
        "id": new_id["ckpt"], "type": "CheckpointLoaderSimple", "pos": [-2580, 4620],
        "size": [360, 120], "flags": {}, "mode": 0,
        "inputs": [widget_input("ckpt_name", "COMBO")],
        "outputs": [{"name": "MODEL", "type": "MODEL", "links": []},
                    {"name": "CLIP", "type": "CLIP", "links": []},
                    {"name": "VAE", "type": "VAE", "links": []}],
        "properties": {"Node name for S&R": "CheckpointLoaderSimple"},
        "widgets_values": [ckpt],
    })

    # --- CLIPTextEncode positive / negative ---
    for key, out_name, text in (("pos", "CLIP", plan["keyframe_prompt"]),
                                ("neg", "CLIP", plan["keyframe_negative"])):
        link = new_link(new_id["ckpt"], 1, new_id[key], 1, "CLIP")
        wf["nodes"].append({
            "id": new_id[key], "type": "CLIPTextEncode", "pos": [-2580, 4760 if key == "pos" else 4960],
            "size": [360, 160], "flags": {}, "mode": 0,
            "inputs": [widget_input("text", "STRING"), widget_input("clip", "CLIP", link)],
            "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": []}],
            "properties": {"Node name for S&R": "CLIPTextEncode"},
            "widgets_values": [text],
        })

    # --- EmptyLatentImage (width/height derived from ResolutionSelector) ---
    lw = new_link(sel["id"], 0, new_id["latent"], 0, "INT") if sel else None
    lh = new_link(sel["id"], 1, new_id["latent"], 1, "INT") if sel else None
    latent_inputs = [widget_input("width", "INT", lw), widget_input("height", "INT", lh),
                     widget_input("batch_size", "INT")]
    wf["nodes"].append({
        "id": new_id["latent"], "type": "EmptyLatentImage", "pos": [-2580, 5160],
        "size": [360, 110], "flags": {}, "mode": 0,
        "inputs": latent_inputs,
        "outputs": [{"name": "LATENT", "type": "LATENT", "links": []}],
        "properties": {"Node name for S&R": "EmptyLatentImage"},
        "widgets_values": [1],
    })

    # --- KSampler ---
    l_model = new_link(new_id["ckpt"], 0, new_id["ksampler"], 3, "MODEL")
    l_pos = new_link(new_id["pos"], 0, new_id["ksampler"], 4, "CONDITIONING")
    l_neg = new_link(new_id["neg"], 0, new_id["ksampler"], 5, "CONDITIONING")
    l_lat = new_link(new_id["latent"], 0, new_id["ksampler"], 6, "LATENT")
    wf["nodes"].append({
        "id": new_id["ksampler"], "type": "KSampler", "pos": [-2580, 5400],
        "size": [360, 260], "flags": {}, "mode": 0,
        "inputs": [widget_input("model", "MODEL", l_model),
                   widget_input("positive", "CONDITIONING", l_pos),
                   widget_input("negative", "CONDITIONING", l_neg),
                   widget_input("latent_image", "LATENT", l_lat)],
        "outputs": [{"name": "LATENT", "type": "LATENT", "links": []}],
        "properties": {"Node name for S&R": "KSampler"},
        "widgets_values": [plan["seed"], build.get("sdxl_steps", 28), build.get("sdxl_cfg", 7.0),
                           build.get("sdxl_sampler", "euler"), build.get("sdxl_scheduler", "normal"), 1.0],
    })

    # --- VAEDecode ---
    l_samp = new_link(new_id["ksampler"], 0, new_id["vae_decode"], 0, "LATENT")
    l_vae = new_link(new_id["ckpt"], 2, new_id["vae_decode"], 1, "VAE")
    wf["nodes"].append({
        "id": new_id["vae_decode"], "type": "VAEDecode", "pos": [-2580, 5700],
        "size": [240, 70], "flags": {}, "mode": 0,
        "inputs": [widget_input("samples", "LATENT", l_samp), widget_input("vae", "VAE", l_vae)],
        "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": []}],
        "properties": {"Node name for S&R": "VAEDecode"},
        "widgets_values": [],
    })

    # --- SaveImage (keyframe) ---
    l_img = new_link(new_id["vae_decode"], 0, new_id["save"], 0, "IMAGE")
    wf["nodes"].append({
        "id": new_id["save"], "type": "SaveImage", "pos": [-2580, 5900],
        "size": [360, 130], "flags": {}, "mode": 0,
        "inputs": [widget_input("images", "IMAGE", l_img)],
        "outputs": [],
        "properties": {"Node name for S&R": "SaveImage"},
        "widgets_values": [build.get("keyframe_prefix", "director/keyframes")],
    })

    # --- feed keyframe into the subgraph instance's first_frame input ---
    feed_link = new_link(new_id["vae_decode"], 0, inst["id"], inst_first_frame_slot, "IMAGE")
    inst["inputs"][inst_first_frame_slot]["link"] = feed_link
    inst["inputs"][inst_first_frame_slot]["shape"] = 7

    wf["last_node_id"] = next_id + 6
    wf["last_link_id"] = last_link
    return wf


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build(plan, env=None, cfg=None, first_frame_image=None, reference_images=None):
    """Build the save-format workflow JSON for a normalized plan."""
    cfg = cfg or {}
    w, h = compute_dimensions(plan["aspect"], plan["megapixels"])
    plan = dict(plan)
    plan["_width"] = w
    plan["_height"] = h

    pipeline = plan["pipeline"]
    if pipeline == "t2v":
        return build_t2v(plan, env, cfg)
    if pipeline == "i2v":
        return build_i2v(plan, env, cfg, first_frame_image=first_frame_image)
    if pipeline == "r2v":
        return build_r2v(plan, env, cfg, reference_images=reference_images)
    if pipeline == "sdxl2v":
        return build_sdxl2v(plan, env, cfg)
    raise BuildError(f"未知流水线: {pipeline}")
