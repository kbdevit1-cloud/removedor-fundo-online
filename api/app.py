from fastapi import FastAPI, Request

app = FastAPI()

@app.get('/health')
def health():
    return {'ok': True}

@app.post('/api/remove-bg')
async def process_image(request: Request):
    data = await request.body()
    return {'received': len(data)}
