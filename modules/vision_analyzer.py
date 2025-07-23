"""
modules/vision_analyzer.py   —  e.g. aligned with SiliconFlow official API
dependency:
    pip install pillow requests pyyaml
config/settings.yaml:
    vlm:
      apikey: "YOUR_API_KEY"
"""

import base64, io, os, requests, yaml
from typing import Dict
from PIL import Image

# ------------ public configuration ------------
def _load_cfg():
    if not os.path.isfile("config/settings.yaml"):
        raise FileNotFoundError("shortage of config/settings.yaml")
    with open("config/settings.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg["vlm"]["apikey"]

API_KEY   = _load_cfg()
ROOT_URL  = "https://api.siliconflow.cn"          # Root domain only, without /v1
CHAT_EP   = f"{ROOT_URL}/v1/chat/completions"
FILES_EP  = f"{ROOT_URL}/v1/files"
MODEL     = "Qwen/Qwen2.5-VL-72B-Instruct"

HEADERS_JSON = {"Authorization": f"Bearer {API_KEY}"}

# ------------ helper function ------------
def _img2b64_webp(path: str, max_px: int = 1024) -> str:
    """Scale to 1024 px on the long side, quality 65, return base64 webp"""
    with Image.open(path) as im:
        if max(im.size) > max_px:
            im.thumbnail((max_px, max_px))
        buf = io.BytesIO()
        im.save(buf, format="WEBP", quality=65, method=6)
        return base64.b64encode(buf.getvalue()).decode()

def _prompts(crop: str) -> Dict[str, str]:
    return {
        "growth": (
            f"Please evaluate the current growth status of the {crop} shown in the image. "
            f"Assess based on leaf color, morphology, and overall vigor. "
            f"Use professional agronomic terminology and provide a concise, objective explanation. "
            f"Avoid assumptions not visible in the image."
        ),
        "disease": (
            f"Please determine whether there are any visible signs of disease, pest infestation, or nutrient deficiency "
            f"on the {crop} in the image. Explain your judgment based on observable symptoms only (e.g., spots, discoloration, deformation). "
            f"Do not provide treatments unless explicitly requested."
        ),
        "summary": (
            f"Please summarize the key observation from this {crop} image in 1–2 professional sentences, "
            f"focusing on growth condition and potential agricultural implications."
        )
    }

# ------------ File Upload (batch) ------------
def upload_file(filepath: str, purpose: str = "batch") -> dict:
    """
    Upload files to /v1/files for use by the batch task.
    Returns {"id": "file-xxxx", ...}
    """
    with open(filepath, "rb") as f:
        files = {
            "file": (os.path.basename(filepath), f, "text/plain"),
            "purpose": (None, purpose)
        }
        resp = requests.post(
            FILES_EP,
            headers={"Authorization": f"Bearer {API_KEY}"},
            files=files,
            timeout=60
        )
    resp.raise_for_status()
    return resp.json()

# ------------ Visual analysis of a single image ------------
def _chat_with_image(img_b64: str, prompt: str) -> str:
    payload = {
        "model": MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:image/webp;base64,{img_b64}",
                               "detail": "auto"}},
                {"type": "text", "text": prompt}
            ]
        }]
    }
    resp = requests.post(CHAT_EP, json=payload, headers=HEADERS_JSON, timeout=600)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

def vision_analysis(image_path: str, crop: str = None, crop_type: str = None) -> Dict[str, str]: # type: ignore
    crop = crop or crop_type or "crop（作物）"
    img_b64 = _img2b64_webp(image_path)
    p = _prompts(crop)
    return {
        "growth_analysis":  _chat_with_image(img_b64, p["growth"]),
        "disease_detection":_chat_with_image(img_b64, p["disease"]),
        "image_summary":    _chat_with_image(img_b64, p["summary"])
    }

# ------------------ CLI quick-test ------------------
if __name__ == "__main__":
    res = vision_analysis("demo.jpg", "水稻")
    print(res)
    # file_id = upload_file("requests.txt")
    # print("Uploaded:", file_id)
