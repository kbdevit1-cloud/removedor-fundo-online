# Removedor de Fundo IA Online

Projeto com:

- `frontend/`: site estático para GitHub Pages.
- `backend/`: API FastAPI com `rembg`/U2Net para remover fundo com melhor qualidade.

## Importante

GitHub Pages hospeda apenas o frontend estático. O processamento pesado em Python precisa ficar em um backend separado, por exemplo Render, Railway, VPS ou servidor interno.

## Publicar frontend no GitHub Pages

1. Crie um repositório no GitHub, por exemplo `removedor-fundo-online`.
2. Envie todos estes arquivos para o repositório.
3. Vá em `Settings > Pages`.
4. Em `Build and deployment`, selecione `GitHub Actions`.
5. O workflow `.github/workflows/pages.yml` publica o conteúdo da pasta `frontend/`.

## Publicar backend no Render

1. Crie um Web Service no Render conectado ao mesmo repositório.
2. Use:
   - Root Directory: `backend`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
3. Variáveis opcionais:
   - `REMBG_MODEL=u2net`
   - `CORS_ORIGINS=*`

Depois de publicado, copie a URL do backend, por exemplo:

`https://removedor-fundo-api.onrender.com`

Cole essa URL no campo "URL do backend" no site.

## Rodar localmente

```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --reload
```

Abra `frontend/index.html` e use como URL do backend:

`http://127.0.0.1:8000`
