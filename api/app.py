import base64
import io
import os

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from PIL import Image, ImageEnhance, ImageOps

app = FastAPI(title='Removedor de Fundo IA')

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv('CORS_ORIGINS', '*').split(','),
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)

SESSION = None
REMOVE_FN = None
NEW_SESSION_FN = None


def load_rembg():
    global SESSION, REMOVE_FN, NEW_SESSION_FN
    if REMOVE_FN is None or NEW_SESSION_FN is None:
        from rembg import remove, new_session
        REMOVE_FN = remove
        NEW_SESSION_FN = new_session
    if SESSION is None:
        SESSION = NEW_SESSION_FN(os.getenv('REMBG_MODEL', 'u2net'))
    return REMOVE_FN, SESSION


def improve_quality(img: Image.Image) -> Image.Image:
    rgba = img.convert('RGBA')
    alpha = rgba.getchannel('A')
    rgb = rgba.convert('RGB')
    rgb = ImageOps.autocontrast(rgb, cutoff=1)
    rgb = ImageEnhance.Sharpness(rgb).enhance(1.15)
    rgb = ImageEnhance.Contrast(rgb).enhance(1.05)
    out = rgb.convert('RGBA')
    out.putalpha(alpha)
    return out


def crop_transparent(img: Image.Image) -> Image.Image:
    rgba = img.convert('RGBA')
    bbox = rgba.getbbox()
    if not bbox:
        return rgba
    w, h = rgba.size
    pad = max(8, int(max(w, h) * 0.025))
    left = max(0, bbox[0] - pad)
    top = max(0, bbox[1] - pad)
    right = min(w, bbox[2] + pad)
    bottom = min(h, bbox[3] + pad)
    return rgba.crop((left, top, right, bottom))


@app.get('/')
def root():
    return {'ok': True, 'service': 'removedor-fundo-api'}


@app.get('/health')
def health():
    return {'ok': True}


@app.post('/api/remove-bg')
async def process_image(request: Request):
    try:
        payload = await request.json()
        image_b64 = payload.get('image_base64', '')
        crop = bool(payload.get('crop', True))
        if not image_b64:
            raise HTTPException(status_code=400, detail='Imagem não enviada.')
        if ',' in image_b64:
            image_b64 = image_b64.split(',', 1)[1]
        raw = base64.b64decode(image_b64)
        if len(raw) > 20 * 1024 * 1024:
            raise HTTPException(status_code=413, detail='Imagem muito grande. Limite: 20 MB.')
        img = Image.open(io.BytesIO(raw)).convert('RGBA')
        max_side = 1800
        w, h = img.size
        if max(w, h) > max_side:
            scale = max_side / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        remove_fn, session = load_rembg()
        out_bytes = remove_fn(
            img,
            session=session,
            alpha_matting=True,
            alpha_matting_foreground_threshold=240,
            alpha_matting_background_threshold=10,
            alpha_matting_erode_size=10,
        )
        out = Image.open(io.BytesIO(out_bytes)).convert('RGBA')
        out = improve_quality(out)
        if crop:
            out = crop_transparent(out)
        buf = io.BytesIO()
        out.save(buf, format='PNG')
        return Response(content=buf.getvalue(), media_type='image/png')
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': f'Erro ao processar: {exc}'})
