# Manaus Explorer - Sistema de Recomendação

## 🎯 Objetivo do Sistema
O Manaus Explorer é um sistema de recomendação que sugere itens para usuários com base em suas avaliações anteriores e na similaridade entre usuários. O sistema permite identificar itens relevantes e personalizar sugestões de forma dinâmica, considerando tanto dados históricos quanto avaliações simuladas adicionadas pelos usuários.

---

## ⚙️ Como Executar

### Backend (FastAPI)
- Certifique-se de ter Python 3.11+ instalado.
- Instale as dependências: `fastapi`, `uvicorn`, `pandas`, `numpy`.
- Execute a API usando: `uvicorn main:app --reload`.
- A API ficará disponível em `http://127.0.0.1:8000` e a documentação em `http://127.0.0.1:8000/docs`.

### Frontend (Streamlit)
- Certifique-se de ter Streamlit instalado.
- Instale as dependências: `folium`, `streamlit_folium`, `plotly`, 
- Execute o frontend usando: `streamlit run app.py`.
- O frontend irá buscar os endpoints do backend para exibir gráficos e recomendações.

---

## 🧠 Lógica de Recomendação
O sistema utiliza **filtragem colaborativa baseada em usuários**:

1. Constrói uma matriz usuário × item com as notas das avaliações.
2. Para cada usuário, calcula a **similaridade com todos os outros usuários**.
3. Seleciona os **K usuários mais similares** (vizinhos).
4. Calcula a **média das notas dos vizinhos** para prever a nota de itens não avaliados.
5. Sugere os **top N itens** com maiores notas previstas, respeitando filtros opcionais como localização e preço estimado.

---

## 🔍 Métrica de Similaridade
Foi utilizada a **similaridade do cosseno**, definida como:

\[
\text{similaridade}(u, v) = \frac{u \cdot v}{\|u\| \|v\|}
\]

- Considera a **direção dos vetores de avaliação**, não a magnitude.
- Compara padrões de gosto independentemente da quantidade de avaliações.
- Valoriza **semelhanças de preferência**, mesmo que usuários avaliem em escalas diferentes.

---

## 📊 Cálculo e Análise da Acurácia
A acurácia é medida usando **top-K recomendações e holdout**:

1. Cada usuário elegível deve ter **no mínimo 3 avaliações**.
2. As avaliações são divididas em **treino** e **teste** (holdout de 40%).
3. Para cada usuário:
   - Geramos os **top K itens recomendados** com base no treino.
   - Comparamos com os **itens relevantes** no conjunto de teste (nota ≥ 3).
   - A acurácia é calculada como:
\[
\text{acurácia} = \frac{\text{número de acertos no top-K}}{K}
\]
4. Permite avaliar **quantos itens recomendados são realmente relevantes**.

> O sistema mantém gráficos interativos de acurácia por usuário e distribuição de itens por categoria, que se atualizam conforme novas avaliações são adicionadas.

---

## 📝 Observações
- O backend considera tanto o CSV original (`avaliacoes.csv`) quanto as avaliações temporárias adicionadas via endpoint `/avaliar`.
- É possível expandir o sistema com **filtros adicionais**, **métricas mais complexas** ou **visualizações interativas** usando Plotly.
