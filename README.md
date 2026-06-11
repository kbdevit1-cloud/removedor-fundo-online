# Removedor de Fundo IA Online

Projeto com frontend online e API Python para remover fundo de imagens com melhor qualidade.

## Estrutura

- `frontend/`: site estático para GitHub Pages.
- `api/`: API FastAPI com `rembg`/U2Net.
- `.github/workflows/pages.yml`: workflow para publicar o frontend no GitHub Pages.
- `render.yaml`: configuração para publicar a API no Render.

## Importante

O GitHub Pages hospeda apenas HTML, CSS e JavaScript. Ele não roda Python. Por isso o projeto foi separado em duas partes:

1. **Frontend no GitHub Pages**: tela online para enviar imagem e baixar PNG.
2. **API em Render/Railway/VPS**: processamento Python com IA para remover fundo.

## Publicar frontend no GitHub Pages

1. Vá em `Settings > Pages`.
2. Em `Build and deployment`, selecione `GitHub Actions`.
3. Faça um push/commit na branch `main`.
4. O workflow publica automaticamente a pasta `frontend/`.

## Publicar API no Render

Crie um Web Service no Render usando este repositório.

Configuração recomendada:

- Root Directory: `api`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`

Variáveis opcionais:

- `REMBG_MODEL=u2net`
- `CORS_ORIGINS=*`

Depois de publicar, copie a URL da API e cole no campo **URL do backend** no site.

Exemplo:

```txt
https://removedor-fundo-api.onrender.com
```

## Rodar localmente

```bash
cd api
pip install -r requirements.txt
uvicorn app:app --reload
```

Abra `frontend/index.html` e use como URL do backend:

```txt
http://127.0.0.1:8000
```
