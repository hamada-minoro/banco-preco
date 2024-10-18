import streamlit as st
import requests
import pandas as pd
from PIL import Image
import base64
from io import BytesIO
import time  # Para adicionar um delay entre as tentativas

imagem = Image.open("M.png")  

# Função para converter a imagem em base64
def image_to_base64(image):
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# Função para formatar preço em reais
def formatar_preco_reais(valor):
    if valor is None:
        return 'Preço não disponível'
    else:
        return f'R$ {valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

# URLs atualizadas
consultarItemMaterial_base_url = 'https://dadosabertos.compras.gov.br/modulo-pesquisa-preco/1_consultarMaterial'
consultarItemServico_base_url = 'https://dadosabertos.compras.gov.br/modulo-pesquisa-preco/3_consultarServico'

def obter_itens(tipo_item, codigo_item_catalogo, pagina, tamanho_pagina, estado, max_tentativas=5):
    url = consultarItemMaterial_base_url if tipo_item == 'Material' else consultarItemServico_base_url
    params = {
        'pagina': pagina,
        'tamanhoPagina': tamanho_pagina,
        'codigoItemCatalogo': codigo_item_catalogo,
        'estado': estado if estado != "Todos" else None
    }
    
    tentativas = 0
    
    while tentativas < max_tentativas:
        try:
            response = requests.get(url, params=params)

            if response.status_code == 200:
                json_response = response.json()
                itens = json_response.get('resultado', [])
                paginas_restantes = json_response.get('paginasRestantes', 0)
                total_paginas = json_response.get('totalPaginas', 0)

                if itens:
                    return itens, paginas_restantes, total_paginas
                else:
                    st.warning(f"Consulta retornou vazia. Tentando novamente... (Tentativa {tentativas + 1})")
                    tentativas += 1
                    time.sleep(2)  # Espera 2 segundos antes da próxima tentativa
            else:
                error_message = response.text
                st.error(f"Erro na consulta: {response.status_code} - {error_message}")
                
                # Verifica se é o erro específico que estamos tratando
                if response.status_code == 400 and "Unable to acquire JDBC Connection" in error_message:
                    tentativas += 1
                    st.warning(f"Tentativa {tentativas}/{max_tentativas} falhou. Tentando novamente...")
                    time.sleep(2)  # Espera 2 segundos antes da próxima tentativa
                else:
                    return [], 0  # Retorna uma lista vazia e 0 se ocorrer um erro diferente

        except Exception as e:
            st.error(f"Erro ao realizar a requisição: {str(e)}")
            tentativas += 1  # Incrementa o número de tentativas
            time.sleep(2)  # Espera 2 segundos antes da próxima tentativa

    st.error("Número máximo de tentativas atingido. Nenhum dado foi retornado.")
    return [], 0

# Streamlit UI
st.markdown("""
    <div style='display: flex; flex-direction: column; align-items: center; justify-content:center;'>
        <img src="data:image/png;base64,{}" style='height: 100px; width: 100px'/>
        <h1 style='text-align: center;'>PESQUISA DE PREÇOS</h1>
    </div>
""".format(image_to_base64(imagem)), unsafe_allow_html=True)

tipo_item = st.selectbox("Selecione o tipo de item para consulta", ['Material', 'Serviço'], key='tipo_item')
codigo_item_catalogo = st.text_input("Código do Item de Catálogo", value="", key='codigo_item_catalogo')
estado = st.selectbox("Selecione o estado", ['Todos', 'RJ'], key='estado')
pagina = st.number_input("Indique a página para consulta", min_value=1, value=1, step=1)
tamanho_pagina = st.number_input("Indique o tamanho da página para consulta", min_value=10, value=500, step=1)

if st.button('Consultar'):
    if codigo_item_catalogo:
        itens, paginas_restantes, total_paginas = obter_itens(tipo_item, codigo_item_catalogo, pagina, tamanho_pagina, estado)
        
        if itens:
            st.session_state['itens'] = itens
            st.session_state['paginas_restantes'] = paginas_restantes
            st.session_state['total_paginas'] = total_paginas
            st.write(f"Total de páginas: {total_paginas}")
            st.write(f"Páginas restantes: {paginas_restantes}")            
        else:
            st.error("Nenhum item encontrado ou houve um erro na consulta. Tente novamente mais tarde.")
    else:
        st.warning("Por favor, informe o código do item de catálogo para realizar a consulta.")

if st.session_state.get('itens'):
    try:
        dados = []
        for item in st.session_state['itens']:
            if isinstance(item, dict):
                dados.append({
                    'descricaoItem': item.get('descricaoItem', 'Descrição não disponível'),
                    'codigoItemCatalogo': str(item.get('codigoItemCatalogo', 'Código não disponível')),
                    'precoUnitario': formatar_preco_reais(item.get('precoUnitario', None)),
                    'nomeFornecedor': item.get('nomeFornecedor', 'Fornecedor não disponível'),
                    'nomeUasg': item.get('nomeUasg', 'Uasg não disponível'),
                    'dataCompra': item.get('dataCompra', 'Data não disponível')
                })
            else:
                st.error("Item não é um dicionário. Estrutura inesperada.")

        # Criando o DataFrame e ordenando pela data de compra em ordem decrescente
        df_resultados = pd.DataFrame(dados)
        df_resultados['dataCompra'] = pd.to_datetime(df_resultados['dataCompra'], errors='coerce')

        # Ordenando o DataFrame pela data de compra em ordem decrescente
        df_resultados = df_resultados.sort_values(by='dataCompra', ascending=False)

        # Formatação da data para dd-mm-aaaa
        df_resultados['dataCompra'] = df_resultados['dataCompra'].dt.strftime('%d-%m-%Y')

        if not df_resultados.empty:
            st.dataframe(df_resultados)  # Mostra os resultados em forma de tabela
        else:
            st.error("Nenhum dado encontrado para exibir.")
        
        # Geração do CSV para download
        csv = df_resultados.to_csv(sep=';', index=False).encode('utf-8')
        st.download_button(
            label="Download dos dados em CSV",
            data=csv,
            file_name='dados_consulta.csv',
            mime='text/csv',
        )
    except Exception as e:
        st.error(f"Erro ao processar os itens: {str(e)}")
