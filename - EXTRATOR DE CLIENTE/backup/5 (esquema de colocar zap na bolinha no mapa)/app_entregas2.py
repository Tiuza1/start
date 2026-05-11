import streamlit as st
import streamlit.components.v1 as components  # <--- ADICIONE ESTA LINHA
import pandas as pd
# ... resto dos seus imports
import json
import streamlit as st
import re
import os
import math
import time
import pandas as pd
import urllib.parse

# =================================================================
# 1. CONFIGURAÇÃO DE TELA (UI LIMPA)
# =================================================================
st.set_page_config(page_title="GPS Profissional", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    [data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stToolbar"], footer { display: none !important; }
    .block-container { padding: 0 !important; max-width: 100% !important; margin: 0 !important; }
    iframe { width: 100vw; height: 100vh; border: none !important; }
    </style>
""", unsafe_allow_html=True)

# =================================================================
# 2. LOGICA DE DADOS (PYTHON)
# =================================================================
FILE_SAVE = "progresso_final.json"

if 'lista_pacotes' not in st.session_state: st.session_state.lista_pacotes = []
if 'entregues_id' not in st.session_state: st.session_state.entregues_id = []
if 'ultima_pos' not in st.session_state: st.session_state.ultima_pos = None

def limpar_numero(num):
    num = re.sub(r'\D', '', str(num))
    if not num: return ""
    if not num.startswith('55'): num = '55' + num
    return num

def salvar_progresso():
    dados = {
        "lista_pacotes": st.session_state.lista_pacotes, 
        "entregues_id": st.session_state.entregues_id, 
        "ultima_pos": st.session_state.ultima_pos
    }
    with open(FILE_SAVE, "w") as f: json.dump(dados, f)

if not st.session_state.lista_pacotes and os.path.exists(FILE_SAVE):
    try:
        with open(FILE_SAVE, "r") as f:
            d = json.load(f)
            st.session_state.lista_pacotes = d.get("lista_pacotes", [])
            st.session_state.entregues_id = d.get("entregues_id", [])
            st.session_state.ultima_pos = d.get("ultima_pos")
    except: pass

@st.cache_data
def carregar_banco(mtime): 
    try:
        with open('Lugares marcados.json', 'r', encoding='utf-8') as f:
            dados_j = json.load(f)
        banco = {str(l['properties'].get('title') or l['properties'].get('name')).strip(): 
                (l['geometry']['coordinates'][1], l['geometry']['coordinates'][0]) 
                for l in dados_j.get('features',[])}
        return dict(sorted(banco.items()))
    except: return {}

arquivo_caminho = 'Lugares marcados.json'
mtime = os.path.getmtime(arquivo_caminho) if os.path.exists(arquivo_caminho) else 0
banco_total = carregar_banco(mtime)

# --- AÇÕES VIA URL ---
q = st.query_params
if "add_batch" in q:
    nomes = q["add_batch"].split("|")
    for nome in nomes:
        if nome in banco_total:
            nid = f"{nome}_{time.time_ns()}"
            st.session_state.lista_pacotes.append({
                "id": nid, 
                "nome": nome,
                "cliente": "Adicionado Manualmente",
                "telefone": "",
                "pacote": "Manual",
                "quadra_original": nome
            })
            st.session_state.ultima_pos = banco_total[nome]
    salvar_progresso()
    st.query_params.clear()
    st.rerun()

if "concluir" in q:
    id_p = q["concluir"]
    if id_p not in st.session_state.entregues_id:
        st.session_state.entregues_id.append(id_p)
        for p in st.session_state.lista_pacotes:
            if p['id'] == id_p: st.session_state.ultima_pos = banco_total.get(p['nome'])
        salvar_progresso()
    st.query_params.clear()
    st.rerun()

if "limpar" in q:
    if os.path.exists(FILE_SAVE): os.remove(FILE_SAVE)
    st.session_state.lista_pacotes, st.session_state.entregues_id, st.session_state.ultima_pos = [], [], None
    st.query_params.clear()
    st.rerun()

# =================================================================
# 3. IMPORTADOR AUTOMÁTICO DE CSV
# =================================================================
with st.expander("📦 Importar Planilha de Entregas (CSV)", expanded=False):
    arquivo_csv = st.file_uploader("Selecione o arquivo CSV do aplicativo", type=['csv'])

    if arquivo_csv is not None:
        df = pd.read_csv(arquivo_csv)
        sucessos_data = [] 
        alertas_nao_encontrado = []
        alertas_sem_numero = []
        alertas_cep_invalido = []
        
        if 'Local' not in df.columns or 'CEP' not in df.columns:
            st.error("O arquivo CSV precisa ter as colunas 'Local' e 'CEP' geradas pelo Extrator Pro.")
        else:
            for index, row in df.iterrows():
                local_dump = str(row['Local']).strip()
                cep_dump = str(row['CEP']).strip()
                nome_cli = str(row.get('Nome', 'CLIENTE')).strip()
                tel_cli = limpar_numero(row.get('Telefone', ''))
                pacote_cli = str(row.get('Pacote', 'SEM ID')).strip()
                
                match_numero = re.search(r'(?:QUADRA|QD|Q)\s*(\d+)', local_dump, re.IGNORECASE)
                match_cep = re.search(r'(\d{5})[-.\s]?(\d{3})', cep_dump)
                
                if match_numero and match_cep:
                    numero = str(int(match_numero.group(1)))
                    cep_prefixo = match_cep.group(1)         
                    cep_sufixo = int(match_cep.group(2))     
                    
                    padrao_bairro = ""
                    nome_bairro_amigavel = ""
                    
                    if cep_prefixo in ['72853', '72856']:
                        padrao_bairro = r'p[\.\s]*i*x+'
                        nome_bairro_amigavel = "Parque 9 ou 10"
                    elif cep_prefixo == '72859':
                        if cep_sufixo <= 500:
                            padrao_bairro = r'p[\.\s]*(v\s*i{3}|8)'
                            nome_bairro_amigavel = "Mansões Parque 8"
                        else:
                            padrao_bairro = r'p[\.\s]*(v\s*i{2}|7)'
                            nome_bairro_amigavel = "Mansões Parque 7"
                    else:
                        alertas_cep_invalido.append(f"{local_dump} - CEP: {cep_dump}")
                        continue 
                    
                    regex_busca_banco = rf'^Q\s*0*{numero}\s+{padrao_bairro}$'
                    
                    encontrou_no_banco = False
                    chave_encontrada = ""
                    
                    for chave_banco in banco_total.keys():
                        if re.match(regex_busca_banco, chave_banco, re.IGNORECASE):
                            encontrou_no_banco = True
                            chave_encontrada = chave_banco
                            break
                    
                    if encontrou_no_banco:
                        sucessos_data.append({
                            "quadra_mapa": chave_encontrada,
                            "nome_cli": nome_cli,
                            "tel_cli": tel_cli,
                            "pacote_cli": pacote_cli,
                            "quadra_original": local_dump
                        })
                    else:
                        alertas_nao_encontrado.append(f"{local_dump} (CEP indica {nome_bairro_amigavel})")
                
                elif not match_numero:
                    alertas_sem_numero.append(local_dump)
                else:
                    alertas_cep_invalido.append(f"{local_dump} - CEP vazio ou formato inválido: '{cep_dump}'")
                    
            if sucessos_data:
                st.success(f"✅ {len(sucessos_data)} locais encontrados e validados por CEP!")
                if st.button("🗺️ Adicionar Validados ao Mapa"):
                    for item in sucessos_data:
                        nome_quadra = item["quadra_mapa"]
                        nid = f"{nome_quadra}_{time.time_ns()}"
                        
                        st.session_state.lista_pacotes.append({
                            "id": nid, 
                            "nome": nome_quadra,
                            "cliente": item["nome_cli"],
                            "telefone": item["tel_cli"],
                            "pacote": item["pacote_cli"],
                            "quadra_original": item["quadra_original"]
                        })
                        st.session_state.ultima_pos = banco_total[nome_quadra]
                    salvar_progresso()
                    st.rerun()

            if alertas_nao_encontrado or alertas_sem_numero or alertas_cep_invalido:
                st.warning("⚠️ Alguns endereços não puderam ser mapeados:")
                if alertas_nao_encontrado:
                    for a in alertas_nao_encontrado: st.write(f"- {a}")
                if alertas_cep_invalido:
                    for a in alertas_cep_invalido: st.write(f"- {a}")

# =================================================================
# LÓGICA DE PROXIMIDADE E AGRUPAMENTO
# =================================================================
pendentes_total = [p for p in st.session_state.lista_pacotes if p['id'] not in st.session_state.entregues_id]
proximo_id = None

if st.session_state.ultima_pos and pendentes_total:
    dist_min = float('inf')
    for p in pendentes_total:
        coords = banco_total.get(p['nome'], (0,0))
        d = math.sqrt((st.session_state.ultima_pos[0]-coords[0])**2 + (st.session_state.ultima_pos[1]-coords[1])**2)
        if d < dist_min:
            dist_min = d
            proximo_id = p['id']

agrupado = {}
for p in st.session_state.lista_pacotes:
    nome = p['nome']
    if nome not in agrupado: agrupado[nome] = {"total": 0, "pendentes": []}
    agrupado[nome]["total"] += 1
    if p['id'] not in st.session_state.entregues_id: 
        agrupado[nome]["pendentes"].append(p)

pontos_js = []
for nome, info in agrupado.items():
    coords = banco_total.get(nome, (0,0))
    pendentes_lista = info["pendentes"]
    p_ids = [p['id'] for p in pendentes_lista]
    
    esta_concluido = len(p_ids) == 0
    
    if esta_concluido:
        cor = "#28a745"
    elif any(pid == proximo_id for pid in p_ids):
        cor = "#fd7e14"
    elif len(p_ids) > 1:
        cor = "#007bff"
    else:
        cor = "#dc3545"
    
    num_match = re.findall(r'\d+', nome)
    base_txt = num_match[0] if num_match else nome[:3]
    display_txt = "✔" if esta_concluido else (f"{base_txt} x{len(p_ids)}" if len(p_ids) > 1 else base_txt)

    # PREPARA A LISTA DE TODOS OS CLIENTES DAQUELA QUADRA
    lista_wpp = []
    if not esta_concluido and pendentes_lista:
        for p_info in pendentes_lista:
            lista_wpp.append({
                "id_pacote": p_info['id'],
                "cliente": p_info.get("cliente", "Adicionado Manualmente"),
                "telefone": p_info.get("telefone", ""),
                "pacote": p_info.get("pacote", "Manual"),
                "quadra_real": p_info.get("quadra_original", nome)
            })

    pontos_js.append({
        "id": p_ids[0] if not esta_concluido else "done", 
        "lat": coords[0], "lng": coords[1], 
        "nome": nome, 
        "restantes": len(p_ids),
        "concluido": esta_concluido, 
        "cor": cor, 
        "txt": display_txt,
        "lista_wpp": lista_wpp
    })

total_bolinhas = len(pontos_js)
bolinhas_pendentes = len([p for p in pontos_js if not p['concluido']])

# =================================================================
# 4. HTML/JS
# =================================================================
centro = st.session_state.ultima_pos if st.session_state.ultima_pos else [-16.15, -47.96]
lista_opcoes_html = "".join([f'<option value="{n}">' for n in banco_total.keys()])

mapa_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {{ margin: 0; padding: 0; font-family: sans-serif; overflow: hidden; background: #eee; }}
        #map {{ height: 100vh; width: 100vw; z-index: 1; }}

        .search-container {{
            position: fixed; top: 10px; left: 10px; right: 10px; z-index: 1000;
            background: white; padding: 8px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }}
        .search-row {{ display: flex; gap: 5px; }}
        #input-busca {{ flex: 1; border: 1px solid #ddd; padding: 12px; border-radius: 8px; font-size: 16px; outline: none; }}
        .btn-add {{ background: #007bff; color: white; border: none; padding: 0 20px; border-radius: 8px; font-size: 20px; }}

        #batch-list {{ display: none; flex-wrap: wrap; gap: 5px; margin-top: 8px; padding-top: 8px; border-top: 1px solid #eee; }}
        .batch-item {{ background: #f8f9fa; padding: 4px 10px; border-radius: 15px; font-size: 12px; display: flex; align-items: center; gap: 5px; border: 1px solid #007bff; }}
        .batch-item b {{ color: #d33; cursor: pointer; padding: 0 4px; }}
        .btn-confirm {{ display: none; width: 100%; background: #28a745; color: white; border: none; padding: 12px; border-radius: 8px; font-weight: bold; margin-top: 8px; cursor: pointer; }}

        .count-badge {{
            position: fixed; top: 85px; left: 10px; z-index: 999;
            background: #333; color: white; padding: 8px 15px;
            border-radius: 20px; font-size: 14px; font-weight: bold; box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        }}
        .btn-clear {{
            position: fixed; top: 85px; right: 10px; z-index: 999;
            background: white; border: none; padding: 10px 15px;
            border-radius: 12px; font-size: 14px; font-weight: bold; color: #d33; box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        }}

        /* PAINEL INFERIOR AJUSTADO PARA MULTIPLOS CLIENTES */
        #sheet {{
            position: fixed; bottom: -100%; left: 0; right: 0;
            background: #111; color: white; z-index: 2000; padding: 20px;
            border-radius: 20px 20px 0 0; box-shadow: 0 -5px 25px rgba(0,0,0,0.5);
            transition: bottom 0.4s ease; border-top: 2px solid #333;
            max-height: 85vh; display: flex; flex-direction: column;
        }}
        #sheet.active {{ bottom: 0; }}
        
        .s-header {{ font-size: 20px; font-weight: bold; color: #fff; margin-bottom: 5px; flex-shrink: 0; }}
        .s-sub {{ font-size: 14px; color: #888; margin-bottom: 15px; flex-shrink: 0; }}
        
        /* SCROLL PARA OS CLIENTES */
        #wpp-container {{
            overflow-y: auto; flex: 1; padding-right: 5px; margin-bottom: 10px;
        }}
        #wpp-container::-webkit-scrollbar {{ width: 5px; }}
        #wpp-container::-webkit-scrollbar-thumb {{ background: #444; border-radius: 5px; }}

        .s-cli-name {{ color: #4285F4; font-size: 16px; font-weight: bold; margin-bottom: 2px; }}
        .s-pacote {{ color: #666; font-size: 12px; font-family: monospace; margin-bottom: 10px; }}

        .btn-wpp {{ display: block; background: #000; color: #28a745; text-align: center; border-radius: 8px; border: 1px solid #28a745; text-decoration: none; font-weight: bold; }}
        .btn-chegando {{ display: block; background: #28a745; color: white; text-align: center; border-radius: 8px; text-decoration: none; font-weight: bold; }}
        .btn-rota {{ display: block; background: #000; color: white; text-align: center; border-radius: 8px; text-decoration: none; font-weight: bold; border: 1px solid #444; }}
        
        .btn-concluir-cli {{ display: block; background: #28a745; color: white; text-align: center; padding: 12px 0; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 14px; margin-top: 10px; }}

        .btn-row {{ display: flex; gap: 10px; margin-top: 10px; padding-top: 15px; border-top: 1px solid #333; flex-shrink: 0; }}
        .btn {{ flex: 1; text-align: center; padding: 16px; border-radius: 12px; text-decoration: none; color: white; font-weight: bold; font-size: 14px; border: none; cursor: pointer; }}
        
        .pin {{
            min-width: 38px; height: 38px; padding: 0 8px; border-radius: 19px;
            display: flex; align-items: center; justify-content: center;
            color: white; font-weight: bold; border: 2px solid white; font-size: 13px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3); white-space: nowrap;
        }}
    </style>
</head>
<body>

    <div class="search-container">
        <div class="search-row">
            <input type="text" id="input-busca" list="lugares" placeholder="Adicionar manualmente...">
            <datalist id="lugares">{lista_opcoes_html}</datalist>
            <button class="btn-add" onclick="addToQueue()">➕</button>
        </div>
        <div id="batch-list"></div>
        <button id="btn-confirm-all" class="btn-confirm" onclick="sendBatch()">CONFIRMAR PEDIDOS</button>
    </div>

    <div class="count-badge">📍 {bolinhas_pendentes} restantes</div>
    <button class="btn-clear" onclick="if(confirm('Limpar todas as entregas do mapa?')) window.location.href='?limpar=1'">🗑️ LIMPAR</button>

    <div id="map"></div>

    <div id="sheet">
        <div class="s-header" id="s-nome">Local</div>
        <div class="s-sub" id="s-info"></div>
        
        <!-- LISTA ROLÁVEL DE CLIENTES DESTA QUADRA -->
        <div id="wpp-container"></div>

        <!-- BOTÕES GERAIS INFERIORES -->
        <div class="btn-row">
            <a id="s-gps" href="#" target="_blank" class="btn" style="background:#4285F4">🧭 ABRIR GOOGLE MAPS</a>
        </div>
        <button onclick="closeSheet()" style="width:100%; margin-top:15px; background:none; border:none; color:#777; font-size: 14px; cursor: pointer;">FECHAR PAINEL</button>
    </div>

    <script>
        var map = L.map('map', {{ zoomControl: false, attributionControl: false }}).setView([{centro[0]}, {centro[1]}], 16);
        L.tileLayer('https://mt1.google.com/vt/lyrs=m&x={{x}}&y={{y}}&z={{z}}').addTo(map);

        var queue = [];
        function addToQueue() {{
            var input = document.getElementById('input-busca');
            var val = input.value.trim();
            if(val) {{
                queue.push(val);
                renderQueue();
                input.value = "";
                input.focus();
            }}
        }}
        function removeFromQueue(idx) {{
            queue.splice(idx, 1);
            renderQueue();
        }}
        function renderQueue() {{
            var container = document.getElementById('batch-list');
            var btn = document.getElementById('btn-confirm-all');
            if(queue.length > 0) {{
                container.style.display = "flex";
                btn.style.display = "block";
                container.innerHTML = queue.map((item, i) => 
                    '<div class="batch-item">' + item + '<b onclick="removeFromQueue('+i+')">✕</b></div>'
                ).join('');
            }} else {{
                container.style.display = "none";
                btn.style.display = "none";
            }}
        }}
        function sendBatch() {{
            if(queue.length > 0) {{
                var param = queue.map(encodeURIComponent).join('|');
                window.location.href = "?add_batch=" + param;
            }}
        }}

        var pontos = {json.dumps(pontos_js)};
        function closeSheet() {{ document.getElementById('sheet').classList.remove('active'); }}

        pontos.forEach(function(p) {{
            var icon = L.divIcon({{
                className: '',
                html: '<div class="pin" style="background:'+p.cor+'; opacity:'+(p.concluido ? 0.6 : 1)+'">'+p.txt+'</div>',
                iconSize: [null, 38], iconAnchor: [19, 19]
            }});

            var marker = L.marker([p.lat, p.lng], {{icon: icon}}).addTo(map);
            marker.on('click', function(e) {{
                L.DomEvent.stopPropagation(e);
                
                document.getElementById('s-nome').innerText = p.nome;
                document.getElementById('s-info').innerText = p.concluido ? "Todas as entregas concluídas" : (p.restantes + " pacote(s) pendente(s) aqui");
                
                // LÓGICA DE MÚLTIPLOS CLIENTES NO WHATSAPP
                var wppBox = document.getElementById('wpp-container');
                wppBox.innerHTML = ""; // Limpa o anterior
                
                if(!p.concluido && p.lista_wpp && p.lista_wpp.length > 0) {{
                    wppBox.style.display = "block";
                    
                    p.lista_wpp.forEach(function(cli) {{
                        var nome_exibicao = cli.cliente.toUpperCase();
                        var primeiro_nome = cli.cliente.split(' ')[0] || "Cliente";
                        
                        var htmlCard = '<div style="background: #222; border-left: 4px solid #4285F4; padding: 12px; border-radius: 8px; margin-bottom: 15px;">';
                        htmlCard += '<div class="s-cli-name">👤 ' + nome_exibicao + '</div>';
                        htmlCard += '<div class="s-pacote">📦 Pacote: ' + cli.pacote + '</div>';
                        
                        // Só mostra botões se tiver telefone válido e não for cadastro manual
                        if(cli.telefone && cli.cliente !== "Adicionado Manualmente") {{
                            var msgChegando = encodeURIComponent("Olá " + primeiro_nome + ", Estou chegando no seu endereço (" + cli.quadra_real + "). Tem alguém pra receber a entrega agora?");
                            var msgRota = encodeURIComponent("Oi " + primeiro_nome + ", Seu pacote para a *" + cli.quadra_real + "* está na rota de hoje. Passo até às 17h Ok?");
                            
                            htmlCard += '<div style="display: flex; gap: 8px; margin-bottom: 8px;">';
                            htmlCard += '<a href="https://wa.me/' + cli.telefone + '" target="_blank" class="btn-wpp" style="flex:1; padding:10px 0; font-size:12px;">💬 ZAP</a>';
                            htmlCard += '<a href="https://wa.me/' + cli.telefone + '?text=' + msgChegando + '" target="_blank" class="btn-chegando" style="flex:1; padding:10px 0; font-size:12px;">🚀 CHEGANDO</a>';
                            htmlCard += '</div>';
                            htmlCard += '<a href="https://wa.me/' + cli.telefone + '?text=' + msgRota + '" target="_blank" class="btn-rota" style="padding:10px 0; font-size:12px;">📅 AVISAR ROTA</a>';
                        }} else if (cli.cliente !== "Adicionado Manualmente") {{
                            htmlCard += '<div style="color:#ff4b4b; font-size:12px; margin-bottom:8px;">⚠️ Sem número de telefone no sistema</div>';
                        }}
                        
                        // O BOTÃO DE CONCLUIR FICA DENTRO DO CARD DO CLIENTE
                        htmlCard += '<a href="?concluir=' + cli.id_pacote + '" class="btn-concluir-cli">✅ CONCLUIR ENTREGA</a>';
                        htmlCard += '</div>';
                        
                        wppBox.innerHTML += htmlCard;
                    }});
                }} else {{
                    wppBox.style.display = "none";
                }}
                
                document.getElementById('s-gps').href = "https://www.google.com/maps/dir/?api=1&destination="+p.lat+","+p.lng;
                
                document.getElementById('sheet').classList.add('active');
                map.panTo([p.lat, p.lng]);
            }});
        }});

        map.on('click', closeSheet);
        
        map.locate({{watch: true, enableHighAccuracy: true}});
        var userMarker;
        map.on('locationfound', function(e) {{
            if (!userMarker) {{
                userMarker = L.circleMarker(e.latlng, {{radius: 8, color: 'white', fillColor: '#4285F4', fillOpacity: 1, weight: 3}}).addTo(map);
            }} else {{ userMarker.setLatLng(e.latlng); }}
        }});
    </script>
</body>
</html>
"""

components.html(mapa_html, height=850)
