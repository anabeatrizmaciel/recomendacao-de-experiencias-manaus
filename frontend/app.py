import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import MeasureControl


st.set_page_config(page_title="Manaus Explorer", page_icon="🌴", layout="wide")
API = "http://127.0.0.1:8000"

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
    "Seções", ["✨ Recomendações", "🗺️ Mapa"], index=0 if st.session_state["mode"] == "✨ Recomendações" else 1
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
                    <div style="background:linear-gradient(to right,#B2DFDB,#E0F2F1);padding:15px;border-radius:14px;margin-bottom:10px;box-shadow:3px 3px 7px #B2DFDB;">
                        <h3 style="color:#00695C;margin:0 0 10px 0;">{idx+1}. {icone} {item.get('nome','')}</h3>
                        <p style="margin:0;"><strong>Categoria:</strong> {item.get('categoria','')}</p>
                        <p style="margin:0;"><strong>Localização:</strong> {item.get('localizacao','')}</p>
                        <p style="margin:0;"><strong>Preço estimado:</strong> {item.get('preco_estimado','N/D')}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if st.button("📍 Ver no mapa", key=f"ver_no_mapa_{item.get('id')}_{idx}"):
                    row = itens_df[itens_df["id"].astype(str) == str(item.get("id"))]
                    latlon = coords_from_row(row.iloc[0]) if not row.empty else None
                    if latlon:
                        st.session_state["map_focus"] = {
                            "lat": float(latlon[0]),
                            "lon": float(latlon[1]),
                            "label": f"{item.get('nome','')} • {item.get('localizacao','')}",
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

    m = folium.Map(location=center, zoom_start=zoom, tiles=None, control_scale=True)
    folium.TileLayer(
        tiles="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        name="OpenStreetMap",
        attr="© OpenStreetMap contributors",
        control=True,
        max_zoom=19,
    ).add_to(m)
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

    try:
        st_folium(m, height=620, use_container_width=True, returned_objects=[], key=f"mapa_{hash(str(center))}")
    except Exception:
        components.html(m.get_root().render(), height=620, scrolling=False)

st.markdown("---")
st.markdown(
    "<p style='text-align:center;color:gray'>Projeto de Sistema de Recomendação – Manaus Explorer 🌴</p>",
    unsafe_allow_html=True,
)
