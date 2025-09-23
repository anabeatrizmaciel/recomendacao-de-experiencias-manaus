import streamlit as st
import requests
import pandas as pd

# Configuração da página
st.set_page_config(
    page_title="Manaus Explorer 🌴",
    page_icon="🌴",
    layout="wide"
)

st.markdown("<h1 style='text-align: center; color: #2E8B57;'>Recomendador de Experiências Locais em Manaus 🌴</h1>", unsafe_allow_html=True)
st.markdown("---")

# Carregar itens do CSV
itens_df = pd.read_csv("backend/itens.csv")

# Sidebar - Filtros
st.sidebar.header("Filtros do Usuário")
usuario_id = st.sidebar.number_input("Digite seu ID de usuário:", min_value=1, max_value=12, step=1)
n_recomendacoes = st.sidebar.slider("Número de recomendações:", 1, 10, 5)
localizacao = st.sidebar.selectbox("Localização (opcional):", options=["", "Centro", "Zona Norte", "Zona Sul", "Zona Leste", "Zona Oeste"])
preco = st.sidebar.selectbox("Faixa de preço (opcional):", options=["", "Baixo", "Médio", "Alto"])

# Função para ícones por categoria
def categoria_icone(cat):
    if cat.lower() == "cultura":
        return "🎨"
    elif cat.lower() == "gastronomia":
        return "🍽️"
    elif cat.lower() == "natureza":
        return "🌳"
    elif cat.lower() == "lazer":
        return "🏖️"
    else:
        return "❓"

# Simulação de Avaliação
st.sidebar.markdown("---")
st.sidebar.subheader("Simular Avaliação")
itens_selecionaveis = itens_df.apply(lambda x: f"{x['nome']} ({categoria_icone(x['categoria'])} {x['categoria']} - {x['localizacao']})", axis=1)
item_selecionado = st.sidebar.selectbox("Selecione o item para avaliar:", itens_selecionaveis)
nota_sim = st.sidebar.slider("Nota (0 a 5):", 0.0, 5.0, 3.0, 0.5)
item_id_sim = int(itens_df.iloc[itens_selecionaveis.tolist().index(item_selecionado)]["id"])

if st.sidebar.button("Enviar Avaliação"):
    payload = {"usuario_id": usuario_id, "item_id": item_id_sim, "nota": nota_sim}
    response = requests.post("http://127.0.0.1:8000/avaliar", json=payload)
    if response.status_code == 200:
        st.sidebar.success(response.json()["mensagem"])
    else:
        st.sidebar.error("Erro ao enviar avaliação.")

# Botão principal - Gerar Recomendações
if st.sidebar.button("Gerar Recomendações"):
    payload = {
        "usuario_id": usuario_id,
        "top_n": n_recomendacoes,
        "localizacao": localizacao if localizacao != "" else None,
        "preco_estimado": preco if preco != "" else None
    }
    response = requests.post("http://127.0.0.1:8000/recomendar", json=payload)

    if response.status_code == 200:
        data = response.json()
        recomendacoes = data.get("recomendacoes", [])
        explicacao = data.get("explicacao", "")

        if recomendacoes:
            st.subheader("✨ Experiências recomendadas para você:")

            # Cards em 2 colunas
            cols = st.columns(2)
            for idx, item in enumerate(recomendacoes):
                icone = categoria_icone(item['categoria'])
                with cols[idx % 2]:
                    st.markdown(f"""
                    <div style="background:linear-gradient(to right,#B2DFDB,#E0F2F1); padding:15px; border-radius:15px; margin-bottom:15px; box-shadow:3px 3px 7px #B2DFDB;">
                        <h3 style='color:#00695C;'>{idx+1}. {icone} {item['nome']}</h3>
                        <p><strong>Categoria:</strong> {item['categoria']}</p>
                        <p><strong>Localização:</strong> {item['localizacao']}</p>
                        <p><strong>Preço Estimado:</strong> {item.get('preco_estimado', 'Não disponível')}</p>
                    </div>
                    """, unsafe_allow_html=True)

            # Explicabilidade
            with st.expander("🔎 Por que esses itens foram recomendados?"):
                st.write(explicacao)
        else:
            st.info("Nenhuma recomendação disponível com os filtros escolhidos.")
    else:
        st.error("Erro ao gerar recomendações. Verifique se o backend está rodando.")

st.markdown("---")
st.markdown("<p style='text-align: center; color: gray;'>Projeto de Sistema de Recomendação – Manaus Explorer 🌴</p>", unsafe_allow_html=True)
