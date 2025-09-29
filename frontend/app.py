import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import MeasureControl
import plotly.express as px

st.set_page_config(page_title="Manaus Explorer", page_icon="🌴", layout="wide")
API = "https://recomendacao-de-experiencias-manaus.onrender.com/"

st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(to bottom right, #E8F5E9, #F1F8E9);
    }

    h1, h2, h3 {
        font-family: 'Segoe UI', sans-serif;
    }

    div.stButton > button {
        background: linear-gradient(to right, #2E7D32, #388E3C);
        color: white;
        border-radius: 10px;
        border: none;
        font-weight: bold;
        transition: 0.3s;
    }
    div.stButton > button:hover {
        transform: scale(1.05);
        background: linear-gradient(to right, #1B5E20, #2E7D32);
    }

    .recs-card {
        background: white;
        border-radius: 14px;
        padding: 18px;
        margin-bottom: 14px;
        box-shadow: 2px 2px 8px rgba(0,0,0,0.1);
        transition: 0.2s;
    }
    .recs-card:hover {
        transform: translateY(-4px);
        box-shadow: 4px 4px 14px rgba(0,0,0,0.15);
    }

    section[data-testid="stSidebar"] {
        background: #A5D6A7;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    "<h1 style='text-align:center;color:#2E8B57'>Recomendador de Experiências Locais em Manaus 🌴</h1>",
    unsafe_allow_html=True,
)
st.markdown("---")

@st.cache_data(show_spinner=False)
def load_itens_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, skipinitialspace=True).reset_index(drop=True)
    df.columns = df.columns.str.strip()
    req = ["id", "nome", "categoria", "localizacao", "preco_estimado", "latitude", "longitude"]
    miss = [c for c in req if c not in df.columns]
    if miss:
        raise ValueError(f"Colunas faltando no CSV: {miss}")
    df["lat"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["lon"] = pd.to_numeric(df["longitude"], errors="coerce")
    return df

try:
    itens_df = load_itens_csv("backend/itens.csv")
    if itens_df.dropna(subset=["lat", "lon"]).empty:
        st.error("Nenhuma coordenada válida encontrada no CSV.")
        st.stop()
except Exception as e:
    st.error(f"Erro ao carregar CSV: {e}")
    st.stop()

def coords_from_row(row: pd.Series):
    if pd.notna(row.get("lat")) and pd.notna(row.get("lon")):
        try:
            return float(row["lat"]), float(row["lon"])
        except Exception:
            return None
    return None

def categoria_icone(cat: str):
    cat = (cat or "").lower()
    return {"cultura": "🎨", "gastronomia": "🍽️", "natureza": "🌳", "lazer": "🏖️"}.get(cat, "❓")

st.session_state.setdefault("mode", "✨ Recomendações")
st.session_state.setdefault("recs", [])
st.session_state.setdefault("explicacao", "")
st.session_state.setdefault("map_focus", None)

st.sidebar.header("Filtros do Usuário")
usuario_id = st.sidebar.number_input("ID do usuário:", min_value=1, max_value=12, step=1, value=1)
n_recomendacoes = st.sidebar.slider("Número de recomendações:", 1, 10, 5)
localizacao = st.sidebar.selectbox("Localização (opcional):", ["", "Centro", "Zona Norte", "Zona Sul", "Zona Leste", "Zona Oeste"])
preco = st.sidebar.selectbox("Faixa de preço (opcional):", ["", "Baixo", "Médio", "Alto"])

mode_radio = st.sidebar.radio(
    "Seções",
    ["✨ Recomendações", "🗺️ Mapa", "📊 Análises"],
    index=["✨ Recomendações", "🗺️ Mapa", "📊 Análises"].index(st.session_state["mode"])
    if st.session_state["mode"] in ["✨ Recomendações", "🗺️ Mapa", "📊 Análises"] else 0
)
if mode_radio != st.session_state["mode"]:
    st.session_state["mode"] = mode_radio
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Simular Avaliação")

def label_item(i: int):
    r = itens_df.loc[i]
    return f"{r['nome']} ({categoria_icone(r.get('categoria',''))} {r.get('categoria','')} - {r.get('localizacao','')})"

sel_idx = st.sidebar.selectbox("Item:", options=itens_df.index.tolist(), format_func=label_item)
nota_sim = st.sidebar.slider("Nota (0 a 5):", 0.0, 5.0, 3.0, 0.5)
item_id_sim = int(itens_df.loc[sel_idx, "id"])

if st.sidebar.button("Enviar Avaliação"):
    try:
        r = requests.post(
            f"{API}/avaliar",
            json={"usuario_id": usuario_id, "item_id": item_id_sim, "nota": nota_sim},
            timeout=8,
        )
        r.raise_for_status()
        st.sidebar.success(r.json().get("mensagem", "Avaliação registrada."))
    except requests.exceptions.RequestException as e:
        st.sidebar.error(f"Erro ao enviar avaliação: {e}")

if st.sidebar.button("Gerar Recomendações"):
    payload = {
        "usuario_id": usuario_id,
        "top_n": n_recomendacoes,
        "localizacao": localizacao or None,
        "preco_estimado": preco or None,
    }
    try:
        resp = requests.post(f"{API}/recomendar", json=payload, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        st.session_state["recs"] = data.get("recomendacoes", [])
        st.session_state["explicacao"] = data.get("explicacao", "")
        st.session_state["mode"] = "✨ Recomendações"
        st.rerun()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao gerar recomendações: {e}")

if st.session_state["mode"] == "✨ Recomendações":
    recs = st.session_state["recs"] or []
    if recs:
        st.subheader("✨ Experiências recomendadas para você")
        cols = st.columns(2)

        for idx, item in enumerate(recs):
            icone = categoria_icone(item.get("categoria", ""))
            with cols[idx % 2]:
                st.markdown(
                    f"""
                    <div class=\"recs-card\">\n                        <h3 style=\"color:#2E7D32;margin:0 0 8px 0;\">{idx+1}. {icone} {item.get('nome','')}</h3>\n                        <p><strong>📌 Categoria:</strong> {item.get('categoria','')}</p>\n                        <p><strong>📍 Localização:</strong> {item.get('localizacao','')}</p>\n                        <p><strong>💰 Preço estimado:</strong> {item.get('preco_estimado','N/D')}</p>\n                    </div>\n                    """,
                    unsafe_allow_html=True,
                )

                if st.button("📍 Ver no mapa", key=f"ver_no_mapa_{item.get('id')}_{idx}"):
                    row = itens_df[itens_df["id"].astype(str) == str(item.get("id"))]
                    latlon = coords_from_row(row.iloc[0]) if not row.empty else None
                    if latlon:
                        st.session_state["map_focus"] = {
                            "lat": float(latlon[0]),
                            "lon": float(latlon[1]),
                            "label": f"{item.get('nome','')} • {item.get('localizacao','')}"
                        }
                        st.session_state["mode"] = "🗺️ Mapa"
                        st.rerun()
                    else:
                        st.warning("Este item não possui latitude/longitude válidas no CSV.")

        with st.expander("Por que esses itens?"):
            st.write(st.session_state["explicacao"])
    else:
        st.info("Use a barra lateral para gerar recomendações.")

elif st.session_state["mode"] == "🗺️ Mapa":
    st.subheader("Mapa de Manaus")

    focus = st.session_state.get("map_focus")
    if focus:
        center = [focus["lat"], focus["lon"]]
        zoom = 15
        st.success(f"Mostrando: {focus['label']}  —  Lat {focus['lat']:.6f}, Lon {focus['lon']:.6f}")
    else:
        center = [-3.1190, -60.0217]  
        zoom = 11

    m = folium.Map(location=center, zoom_start=zoom, tiles="CartoDB positron", control_scale=True)
    MeasureControl(position="topleft", primary_length_unit="kilometers").add_to(m)

    df_map = itens_df.copy()
    if localizacao:
        df_map = df_map[df_map["localizacao"] == localizacao]
    if preco:
        df_map = df_map[df_map["preco_estimado"] == preco]

    for _, r in df_map.dropna(subset=["lat", "lon"]).iterrows():
        lat, lon = float(r["lat"]), float(r["lon"])
        is_focus = focus and abs(lat - focus["lat"]) < 1e-6 and abs(lon - focus["lon"]) < 1e-6
        icon = folium.Icon(color=("red" if is_focus else "blue"), icon=("star" if is_focus else "info-sign"))
        popup = folium.Popup(
            f"<b>{r['nome']}</b><br>Categoria: {r.get('categoria','N/D')}<br>Localização: {r.get('localizacao','N/D')}<br>Preço: {r.get('preco_estimado','N/D')}",
            max_width=300,
        )
        folium.Marker([lat, lon], tooltip=r["nome"], popup=popup, icon=icon).add_to(m)

    if st.button("← Voltar para Recomendações", key="voltar_recs"):
        st.session_state["mode"] = "✨ Recomendações"
        st.rerun()

    st_folium(m, height=620, use_container_width=True, returned_objects=[], key=f"mapa_{hash(str(center))}")

elif st.session_state["mode"] == "📊 Análises":
    st.subheader("📊 Análises do Sistema")

    try:
        resp_cat = requests.get(f"{API}/categorias", timeout=8)
        resp_cat.raise_for_status()
        data_cat = resp_cat.json()

        if data_cat:
            df_cat = pd.DataFrame({"Categoria": list(data_cat.keys()), "Quantidade": list(data_cat.values())})
            fig_cat = px.pie(df_cat, names='Categoria', values='Quantidade',
                            color='Categoria', color_discrete_sequence=px.colors.qualitative.Pastel,
                            title="Distribuição de Itens por Categoria")
            fig_cat.update_traces(textinfo='percent+label')
            fig_cat.update_layout(height=500, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_cat, use_container_width=True)
        else:
            st.info("Nenhuma categoria encontrada.")
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao carregar categorias: {e}")

    try:
        resp_acc = requests.get(f"{API}/acuracia", timeout=12)
        resp_acc.raise_for_status()
        data_acc = resp_acc.json()
        usuarios = data_acc.get("usuarios", [])

        usuarios_validos = [u for u in usuarios if u.get("acuracia") is not None]
        if usuarios_validos:
            df_acc = pd.DataFrame([
                {"Usuário": u["usuario_id"], "Acurácia": u["acuracia"]}
                for u in usuarios_validos
            ])
            fig_acc = px.bar(df_acc, x='Usuário', y='Acurácia',
                            text='Acurácia',
                            color='Acurácia', color_continuous_scale='greens',
                            title="Acurácia por Usuário")
            fig_acc.update_layout(yaxis=dict(range=[0,1]), height=500, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            fig_acc.update_traces(texttemplate='%{text:.2f}', textposition='outside')
            st.plotly_chart(fig_acc, use_container_width=True)

            media_acc = df_acc['Acurácia'].mean()
            st.markdown(
                f"📊 Usuários com acurácia maior que a média ({media_acc:.2f}) têm histórico mais consistente. "
                f"Usuários com acurácia menor geralmente têm menos avaliações ou preferências mais variadas."
            )
        else:
            st.info("Nenhum usuário com acurácia calculada.")
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao carregar acurácia: {e}")

st.markdown("---")
st.markdown(
    """
    <div style="text-align:center;color:gray;">
        <p><b>Manaus Explorer 🌴</b> — Sistema de Recomendação de Experiências Locais</p>
        <p>Feito com ❤️ usando Streamlit, Folium e Plotly</p>
    </div>
    """,
    unsafe_allow_html=True,
)
