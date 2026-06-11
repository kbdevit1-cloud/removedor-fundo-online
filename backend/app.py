import io
import os
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from rembg import remove, new_session

app = FastAPI(title="Removedor de Fundo IA")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSION = None


def get_session():
    global SESSION
    if SESSION is None:
        # u2netp é mais leve; u2net costuma ser melhor, porém mais pesado.
        model = os.getenv("REMBG_MODEL", "u2net")
        SESSION = new_session(model)
    return SESSION


def pil_to_cv_rgba(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img.convert("RGBA")), cv2.COLOR_RGBA2BGRA)


def cv_rgba_to_pil(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGRA2RGBA))


def denoise_rgb(img: Image.Image) -> Image.Image:
    """Reduz ruído fino sem destruir tanto a peça/texto."""
    rgb = np.array(img.convert("RGB"))
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    den = cv2.fastNlMeansDenoisingColored(bgr, None, 4, 4, 7, 21)
    den = cv2.bilateralFilter(den, 5, 35, 35)
    out = cv2.cvtColor(den, cv2.COLOR_BGR2RGB)
    return Image.fromarray(out)


def improve_quality(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    alpha = img.getchannel("A")
    rgb = img.convert("RGB")
    rgb = ImageOps.autocontrast(rgb, cutoff=1)
    rgb = ImageEnhance.Sharpness(rgb).enhance(1.18)
    rgb = ImageEnhance.Contrast(rgb).enhance(1.05)
    rgba = rgb.convert("RGBA")
    rgba.putalpha(alpha)
    return rgba


def refine_alpha(img: Image.Image, strength: int = 2) -> Image.Image:
    """Limpa máscara: remove ilhas pequenas, fecha falhas e suaviza borda."""
    rgba = pil_to_cv_rgba(img)
    alpha = rgba[:, :, 3]

    # Remove alpha baixo e normaliza alpha alto.
    _, mask = cv2.threshold(alpha, 80, 255, cv2.THRESH_BINARY)

    # Morfologia: remove sujeira fina e fecha falhas pequenas.
    k = max(1, int(strength))
    kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1))
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 3, 2 * k + 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_open, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close, iterations=1)

    # Mantém componentes relevantes e remove pontinhos soltos.
    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num > 1:
        areas = stats[1:, cv2.CC_STAT_AREA]
        largest = int(np.max(areas)) if len(areas) else 0
        min_area = max(25, int(largest * 0.003))
        clean = np.zeros_like(mask)
        for label in range(1, num):
            area = stats[label, cv2.CC_STAT_AREA]
            if area >= min_area:
                clean[labels == label] = 255
        mask = clean

    # Suaviza borda com blur leve.
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=0.8, sigmaY=0.8)
    rgba[:, :, 3] = mask
    return cv_rgba_to_pil(rgba)


def crop_transparent(img: Image.Image, pad_ratio: float = 0.025) -> Image.Image:
    rgba = img.convert("RGBA")
    alpha = np.array(rgba.getchannel("A"))
    ys, xs = np.where(alpha > 5)
    if len(xs) == 0 or len(ys) == 0:
        return rgba
    w, h = rgba.size
    pad = max(8, int(max(w, h) * pad_ratio))
    left = max(0, int(xs.min()) - pad)
    top = max(0, int(ys.min()) - pad)
    right = min(w, int(xs.max()) + pad)
    bottom = min(h, int(ys.max()) + pad)
    return rgba.crop((left, top, right + 1, bottom + 1))


def clean_internal_speckles(img: Image.Image) -> Image.Image:
    """Filtro leve para ruído visual dentro do objeto, sem apagar o objeto."""
    rgba = img.convert("RGBA")
    alpha = rgba.getchannel("A")
    rgb = rgba.convert("RGB")
    arr = np.array(rgb)
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    # Denoise leve; não remove marcações grandes, só granulação fina.
    den = cv2.fastNlMeansDenoisingColored(bgr, None, 3, 3, 7, 15)
    den = cv2.cvtColor(den, cv2.COLOR_BGR2RGB)
    out = Image.fromarray(den).convert("RGBA")
    out.putalpha(alpha)
    return out


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/api/remove-bg")
async def remove_bg(
    image: UploadFile = File(...),
    denoise: bool = Form(True),
    clean_speckles: bool = Form(True),
    crop: bool = Form(True),
    mask_strength: int = Form(2),
):
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Envie uma imagem PNG, JPG ou JPEG.")

    raw = await image.read()
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Imagem muito grande. Limite: 20 MB.")

    try:
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        # Redimensiona imagens muito grandes para evitar lentidão/memória.
        max_side = 2200
        w, h = img.size
        if max(w, h) > max_side:
            scale = max_side / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        if denoise:
            base_rgb = denoise_rgb(img)
            base_rgb.putalpha(img.getchannel("A"))
            img = base_rgb.convert("RGBA")

        # Alpha matting ajuda a borda, principalmente fotos em fundo claro.
        out_bytes = remove(
            img,
            session=get_session(),
            alpha_matting=True,
            alpha_matting_foreground_threshold=240,
            alpha_matting_background_threshold=10,
            alpha_matting_erode_size=10,
        )
        out = Image.open(io.BytesIO(out_bytes)).convert("RGBA")

        out = refine_alpha(out, strength=max(1, min(mask_strength, 4)))
        if clean_speckles:
            out = clean_internal_speckles(out)
        out = improve_quality(out)
        if crop:
            out = crop_transparent(out)

        buf = io.BytesIO()
        out.save(buf, format="PNG")
        return Response(content=buf.getvalue(), media_type="image/png")
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Erro ao processar: {exc}"})
