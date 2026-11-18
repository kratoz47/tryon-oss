"""Validate selectable body descriptions and compile one versioned avatar prompt."""
import hashlib
import json
import math
from pathlib import Path

CONFIG = json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8"))
PROMPT_VERSION = "body-description-v1"
FIELDS = {field["key"]: field for field in CONFIG["fields"]}
APPEARANCE = {
    "preserve": "Keep the person's gender presentation and visual appearance as shown in the reference photo.",
    "female": "Use a feminine adult appearance while preserving the person's recognizable facial identity.",
    "male": "Use a masculine adult appearance while preserving the person's recognizable facial identity.",
}
POSE = {
    "front": "Stand squarely facing the camera, arms naturally relaxed slightly away from the torso, with both feet visible.",
    "angle": "Stand at a slight three-quarter angle, arms relaxed, weight resting naturally on one leg, with both feet visible.",
}


def public_config():
    return {"version": CONFIG["version"], "prompt_version": PROMPT_VERSION,
            "fields": [{k: v for k, v in field.items() if k != "options"} |
                       {"options": [{"value": o["value"], "label": o["label"]} for o in field["options"]]}
                       for field in CONFIG["fields"]]}


def validate(profile, source="face"):
    if source not in ("face", "full") or not isinstance(profile, dict):
        raise ValueError("身形设置格式无效。")
    if set(profile) - (set(FIELDS) | {"height"}):
        raise ValueError("包含无法识别的身形设置。")
    result = {}
    for key, field in FIELDS.items():
        value = profile.get(key, field["default"])
        if not isinstance(value, str) or value not in {o["value"] for o in field["options"]}:
            raise ValueError("请选择有效的" + field["label"] + "。")
        if key == "build" and value == "preserve" and source != "full":
            raise ValueError("仅凭头像无法保留照片中的全身体型，请选择整体体型。")
        result[key] = value
    height = profile.get("height")
    if height is not None:
        if isinstance(height, bool) or not isinstance(height, (int, float)) or not math.isfinite(height) or not 80 <= height <= 250:
            raise ValueError("身高请输入 80–250 之间的厘米数，或留空。")
        result["height"] = round(height, 1)
    else:
        result["height"] = None
    return result


def from_legacy(body):
    if body not in ("narrow", "medium", "broad"):
        raise ValueError("请选择身形。")
    return validate({"build": "slender" if body == "narrow" else "medium",
                     "shoulder": "broad" if body == "broad" else "natural"})


def compile_prompt(profile, appearance, pose, source="face"):
    profile = validate(profile, source)
    if appearance not in APPEARANCE or pose not in POSE:
        raise ValueError("请选择有效的外观与站姿。")
    clauses = [
        "Generate exactly one photorealistic full-length portrait of the adult person in the reference image.",
        "Preserve recognizable facial identity, hair and skin tone. " + APPEARANCE[appearance],
        ("The full-body photo supplies the person's identity and base anatomy; apply only the explicitly selected body targets."
         if source == "full" else
         "The cropped portrait supplies identity only. Do not infer the entire body from the portrait's visible shoulders."),
        "BODY TARGETS: the overall build is the base; each explicitly selected regional or proportion description below overrides only its own region.",
    ]
    for key, field in FIELDS.items():
        description = next(o["prompt"] for o in field["options"] if o["value"] == profile[key])
        if description:
            clauses.append(description)
    if profile["height"] is not None:
        clauses.append(f"The user's stated height is approximately {profile['height']:g} cm; respect plausible proportions without printing a scale or claiming measurement accuracy.")
    clauses += [POSE[pose],
                "Use a level camera with natural perspective, an evenly lit plain neutral studio background, and clear margins above the hair and below both shoes.",
                "Wear a plain fitted crew-neck T-shirt, plain dark full-length trousers and simple low-top shoes, without shaping garments or loose clothes hiding the silhouette.",
                "Do not automatically beautify the body, cinch the waist, slim the limbs or lengthen legs beyond the explicitly selected targets. Keep anatomy natural.",
                "Return one realistic photograph with no text, measurements, UI, diagrams or watermarks."]
    prompt = " ".join(clauses)
    return profile, prompt, hashlib.sha256(prompt.encode()).hexdigest()
