from fastapi import FastAPI, Query
from pydantic import BaseModel
import pandas as pd
import numpy as np
import math

app = FastAPI()

# Carregar datasets
itens = pd.read_csv("backend/itens.csv")
avaliacoes = pd.read_csv("backend/avaliacoes.csv")

# Guardar avaliações temporárias
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


def usuarios_acuracia(min_avaliacoes: int = 3):
    av = avaliacoes.copy()
    av.columns = [c.strip().lower() for c in av.columns]  # normaliza colunas

    contagem = (
        av.groupby("usuario_id")["item_id"]
          .count()
          .reset_index(name="qtd_avaliacoes")
    )

    elegiveis_df = contagem[contagem["qtd_avaliacoes"] >= min_avaliacoes] \
                    .sort_values(["qtd_avaliacoes", "usuario_id"],
                                 ascending=[False, True])

    return elegiveis_df


@app.get("/usuarios-elegiveis")
def listar_usuarios_elegiveis(min_avaliacoes: int = Query(3, ge=1)):
    df = usuarios_acuracia(min_avaliacoes=min_avaliacoes)
    usuarios = [
        {"usuario_id": int(row.usuario_id),
         "qtd_avaliacoes": int(row.qtd_avaliacoes)}
        for _, row in df.iterrows()
    ]
    return {
        "min_avaliacoes": min_avaliacoes,
        "total": len(usuarios),
        "usuarios": usuarios
    }


def divisao_conjuntos(usuario_id: int, holdout: float = 0.4, min_test: int = 1, seed: int | None = None):
    av = avaliacoes.copy()
    av.columns = [c.strip().lower() for c in av.columns]

    A_u = av[av["usuario_id"] == usuario_id]
    n = len(A_u)
    if n < 3:
        return None, None, {"erro": "Usuário com poucas avaliações para holdout (< 3)."}

    test_size = max(min_test, math.ceil(n * holdout))
    teste_idx = set(A_u.sample(n=test_size, random_state=seed).index.tolist())

    treino_df = av.drop(index=teste_idx)
    teste_df  = A_u.loc[list(teste_idx)]
    return treino_df, teste_df, None


@app.get("/divisao_dataset")
def print_divisao_conjuntos():
    HOLDOUT = 0.4
    MIN_TEST = 1
    MIN_AVALIACOES = 3
    SEED_BASE = 42  

    eleg = usuarios_acuracia(min_avaliacoes=MIN_AVALIACOES)
    user_ids = eleg["usuario_id"].astype(int).tolist()

    resumo = []
    for uid in user_ids:
        seed = SEED_BASE + uid
        treino_df, teste_df, err = divisao_conjuntos(
            uid, holdout=HOLDOUT, min_test=MIN_TEST, seed=seed
        )
        if err:
            resumo.append({
                "usuario_id": uid,
                "erro": err["erro"],
                "qtd_treino": 0,
                "qtd_teste": 0
            })
            continue

        qtd_treino_u = int((treino_df["usuario_id"] == uid).sum())
        qtd_teste_u  = int(teste_df.shape[0])  

        resumo.append({
            "usuario_id": uid,
            "qtd_treino": qtd_treino_u,
            "qtd_teste": qtd_teste_u
        })

    return {
        "parametros_fixos": {
            "holdout": HOLDOUT,
            "min_test": MIN_TEST,
            "min_avaliacoes": MIN_AVALIACOES,
            "seed_base": SEED_BASE
        },
        "total_usuarios": len(user_ids),
        "usuarios": resumo
    }


def topk_RECOMENDACAO(usuario_id: int, av_df: pd.DataFrame, K_top: int = 5, K_viz: int = 3):
   
    matriz = av_df.pivot_table(index="usuario_id", columns="item_id", values="nota").fillna(0)
    if usuario_id not in matriz.index:
        return []

    alvo = matriz.loc[usuario_id].values

    similaridades = {}
    for u in matriz.index:
        if u != usuario_id:
            num = np.dot(alvo, matriz.loc[u].values)
            den = np.linalg.norm(alvo) * np.linalg.norm(matriz.loc[u].values)
            similaridades[u] = (num / den) if den != 0 else 0.0

    vizinhos = [u for u, s in sorted(similaridades.items(), key=lambda x: x[1], reverse=True)[:K_viz] if s > 0]
    if not vizinhos:
        return []

    notas_preditas = matriz.loc[vizinhos].mean().sort_values(ascending=False)

    avaliados = set(av_df[av_df.usuario_id == usuario_id].item_id)
    candidatos = [int(i) for i in notas_preditas.index if i not in avaliados]

    return candidatos[:K_top]


# helper: id -> nome do item (ou "Item <id>")
def nome_do_item(item_id: int) -> str:
    row = itens.loc[itens["id"] == item_id]
    if not row.empty:
        # ajuste o nome da coluna conforme seu CSV (ex.: "nome", "titulo", "atracao")
        return str(row.iloc[0].get("nome", f"Item {item_id}"))
    return f"Item {item_id}"


@app.get("/acuracia")
def calculo_acuracia():
    K_TOP = 5
    K_VIZ = 3
    HOLDOUT = 0.4
    LIMIAR_PADRAO = 3.0   
    MIN_AVALIACOES = 3
    SEED_BASE = 42

    eleg = usuarios_acuracia(min_avaliacoes=MIN_AVALIACOES)
    user_ids = eleg["usuario_id"].astype(int).tolist()

    usuarios_fmt = []

    for uid in user_ids:
        seed = SEED_BASE + uid
        treino_df, teste_df, err = divisao_conjuntos(uid, holdout=HOLDOUT, min_test=1, seed=seed)

        if err:
            usuarios_fmt.append({
                "usuario_id": uid,
                **err,
                "topK": [],
                "relevantes": [],
                "acertos": 0,
                "acuracia": None
            })
            continue

        topK_ids = topk_RECOMENDACAO(uid, treino_df, K_top=K_TOP, K_viz=K_VIZ)

        limiar_usuario = LIMIAR_PADRAO

        relevantes = sorted(set(
            teste_df[teste_df["nota"] >= limiar_usuario]["item_id"].tolist()
        ))

        acertos = sum(1 for iid in topK_ids if iid in relevantes)
        acuracia = round(acertos / K_TOP, 4) if K_TOP > 0 else 0.0

        usuarios_fmt.append({
            "usuario_id": uid,
            "top5 recomendações": [{"nome": nome_do_item(iid)} for iid in topK_ids],
            "relevantes": [{"nome": nome_do_item(iid)} for iid in relevantes],
            "acertos": acertos,
            "acuracia": acuracia
        })

    return {
        "parametros": {
            "K_top5 recomendações": K_TOP,
            "K_viz": K_VIZ,
            "holdout": HOLDOUT,
            "limiar": LIMIAR_PADRAO,
            "min_avaliacoes": MIN_AVALIACOES
        },
        "total_usuarios": len(user_ids),
        "usuarios": usuarios_fmt
    }


# Função de similaridade cosseno
def cosine_similarity(u, v):
    num = np.dot(u, v)
    den = np.linalg.norm(u) * np.linalg.norm(v)
    return num / den if den != 0 else 0


# Endpoint para adicionar avaliação simulada
@app.post("/avaliar")
def avaliar(av: AvaliacaoSimulada):
    global avaliacoes_temp
    avaliacoes_temp = pd.concat([avaliacoes_temp, pd.DataFrame([av.dict()])], ignore_index=True)
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

    notas_preditas = matriz.loc[vizinhos].mean().sort_values(ascending=False)
    avaliados = set(matriz_av[matriz_av.usuario_id == req.usuario_id].item_id)
    candidatos = [i for i in notas_preditas.index if i not in avaliados]

    df_candidatos = itens[itens.id.isin(candidatos)]

    if req.localizacao:
        df_candidatos = df_candidatos[df_candidatos.localizacao.str.contains(req.localizacao, case=False)]
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
