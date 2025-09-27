from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd
import numpy as np
import os

app = FastAPI()

# Caminho dos arquivos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ITENS_PATH = os.path.join(BASE_DIR, "itens.csv")
AVALIACOES_PATH = os.path.join(BASE_DIR, "avaliacoes.csv")
AVALIACOES_TEMP_PATH = os.path.join(BASE_DIR, "avaliacoes_temp.csv")

# Carregar datasets
itens = pd.read_csv(ITENS_PATH)
avaliacoes = pd.read_csv(AVALIACOES_PATH)

# Carregar avaliações temporárias salvas, se existir
if os.path.exists(AVALIACOES_TEMP_PATH):
    avaliacoes_temp = pd.read_csv(AVALIACOES_TEMP_PATH)
else:
    avaliacoes_temp = pd.DataFrame(columns=avaliacoes.columns)

class RecomendacaoRequest(BaseModel):
    usuario_id: int
    top_n: int = 5
    localizacao: str | None = None
    preco_estimado: str | None = None

class AvaliacaoSimulada(BaseModel):
    usuario_id: int
    item_id: int
    nota: float

# Função de similaridade cosseno
def cosine_similarity(u, v):
    num = np.dot(u, v)
    den = np.linalg.norm(u) * np.linalg.norm(v)
    return num / den if den != 0 else 0

# Endpoint raiz
@app.get("/")
def root():
    return {"mensagem": "API do Manaus Explorer está rodando 🚀. Use /docs para ver os endpoints."}

# Endpoint para adicionar avaliação simulada
@app.post("/avaliar")
def avaliar(av: AvaliacaoSimulada):
    global avaliacoes_temp
    nova_av = pd.DataFrame([av.dict()])
    avaliacoes_temp = pd.concat([avaliacoes_temp, nova_av], ignore_index=True)

    # ✅ salvar no CSV sempre que adicionar
    avaliacoes_temp.to_csv(AVALIACOES_TEMP_PATH, index=False)

    return {"mensagem": f"Avaliação do usuário {av.usuario_id} para item {av.item_id} adicionada."}


# Função de recomendação
def recomendar(req: RecomendacaoRequest):
    # Combinar avaliações originais + temporárias
    matriz_av = pd.concat([avaliacoes, avaliacoes_temp], ignore_index=True)

    # Criar matriz usuário-item
    matriz = matriz_av.pivot_table(index="usuario_id", columns="item_id", values="nota").fillna(0)

    if req.usuario_id not in matriz.index:
        return {"recomendacoes": [], "explicacao": f"Usuário {req.usuario_id} não encontrado."}

    alvo = matriz.loc[req.usuario_id].values
    similaridades = {}

    for u in matriz.index:
        if u != req.usuario_id:
            similaridades[u] = cosine_similarity(alvo, matriz.loc[u].values)

    vizinhos = [u for u, s in sorted(similaridades.items(), key=lambda x: x[1], reverse=True)[:3] if s > 0]

    if not vizinhos:
        return {"recomendacoes": [], "explicacao": "Não encontramos usuários semelhantes."}

    notas_preditas = matriz.loc[vizinhos].mean().sort_values(ascending=False)
    avaliados = set(matriz_av[matriz_av.usuario_id == req.usuario_id].item_id)
    candidatos = [i for i in notas_preditas.index if i not in avaliados]

    df_candidatos = itens[itens.id.isin(candidatos)]

    if req.localizacao:
        df_candidatos = df_candidatos[df_candidatos.localizacao.fillna("").str.contains(req.localizacao, case=False)]
    if req.preco_estimado:
        df_candidatos = df_candidatos[df_candidatos.preco_estimado.str.lower() == req.preco_estimado.lower()]
    top_itens = df_candidatos.head(req.top_n).to_dict(orient="records")

    return {
        "recomendacoes": top_itens,
        "explicacao": f"Recomendamos estes itens porque você é semelhante aos usuários {vizinhos}"
    }
@app.post("/recomendar")
def recomendar_endpoint(req: RecomendacaoRequest):
    return recomendar(req)
