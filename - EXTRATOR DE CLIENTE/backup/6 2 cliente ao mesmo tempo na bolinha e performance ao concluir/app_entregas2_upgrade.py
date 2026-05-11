import json
import streamlit as st
import streamlit.components.v1 as components
import re
import os
import math
import time
import pandas as pd

st.set_page_config(page_title="GPS Profissional UX", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
[data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stToolbar"], footer { display: none !important; }
.block-container { padding: 0 !important; max-width: 100% !important; margin: 0 !important; }
iframe { width: 100vw; height: 100vh; border: none !important; }
</style>
""", unsafe_allow_html=True)

FILE_SAVE = "progresso_final.json"
DEFAULT_CENTER = [-16.15, -47.96]
DEFAULT_ZOOM = 16

if 'lista_pacotes' not in st.session_state: st.session_state.lista_pacotes = []
if 'entregues_id' not in st.session_state: st.session_state.entregues_id = []
if 'ultima_pos' not in st.session_state: st.session_state.ultima_pos = None
if 'map_center' not in st.session_state: st.session_state.map_center = DEFAULT_CENTER
if 'map_zoom' not in st.session_state: st.session_state.map_zoom = DEFAULT_ZOOM


def limpar_numero(num):
    num = re.sub(r'\D', '', str(num))
    if not num:
        return ""
    if not num.startswith('55'):
        num = '55' + num
    return num


def salvar_progresso():
    dados = {
        "lista_pacotes": st.session_state.lista_pacotes,
        "entregues_id": st.session_state.entregues_id,
        "ultima_pos": st.session_state.ultima_pos,
        "map_center": st.session_state.map_center,
        "map_zoom": st.session_state.map_zoom
    }
    with open(FILE_SAVE, "w", encoding="utf-8") as f:
        json.dump(dados, f)


if not st.session_state.lista_pacotes and os.path.exists(FILE_SAVE):
    try:
        with open(FILE_SAVE, "r", encoding="utf-8") as f:
            d = json.load(f)
            st.session_state.lista_pacotes = d.get("lista_pacotes", [])
            st.session_state.entregues_id = d.get("entregues_id", [])
            st.session_state.ultima_pos = d.get("ultima_pos")
            st.session_state.map_center = d.get("map_center", DEFAULT_CENTER)
            st.session_state.map_zoom = d.get("map_zoom", DEFAULT_ZOOM)
    except:
        pass


@st.cache_data
def carregar_banco(mtime):
    candidatos = ['Lugares marcados.json', 'Lugares-marcados.json']
    for arquivo in candidatos:
        if os.path.exists(arquivo):
            try:
                with open(arquivo, 'r', encoding='utf-8') as f:
                    dados_j = json.load(f)
                banco = {
                    str(l['properties'].get('title') or l['properties'].get('name')).strip():
                    (l['geometry']['coordinates'][1], l['geometry']['coordinates'][0])
                    for l in dados_j.get('features', [])
                }
                return dict(sorted(banco.items()))
            except:
                pass
    return {}


arquivo_caminho = 'Lugares marcados.json' if os.path.exists('Lugares marcados.json') else 'Lugares-marcados.json'
mtime = os.path.getmtime(arquivo_caminho) if os.path.exists(arquivo_caminho) else 0
banco_total = carregar_banco(mtime)

q = st.query_params

if "map_lat" in q and "map_lng" in q:
    try:
        st.session_state.map_center = [float(q["map_lat"]), float(q["map_lng"])]
    except:
        pass
if "map_zoom" in q:
    try:
        st.session_state.map_zoom = int(float(q["map_zoom"]))
    except:
        pass

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
            if p['id'] == id_p:
                st.session_state.ultima_pos = banco_total.get(p['nome'])
                break
        salvar_progresso()
    st.query_params.clear()
    st.rerun()

if "desfazer" in q:
    id_p = q["desfazer"]
    if id_p in st.session_state.entregues_id:
        st.session_state.entregues_id = [x for x in st.session_state.entregues_id if x != id_p]
        salvar_progresso()
    st.query_params.clear()
    st.rerun()

if "limpar" in q:
    if os.path.exists(FILE_SAVE):
        os.remove(FILE_SAVE)
    st.session_state.lista_pacotes = []
    st.session_state.entregues_id = []
    st.session_state.ultima_pos = None
    st.session_state.map_center = DEFAULT_CENTER
    st.session_state.map_zoom = DEFAULT_ZOOM
    st.query_params.clear()
    st.rerun()

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
            for _, row in df.iterrows():
                local_dump = str(row['Local']).strip()
                cep_dump = str(row['CEP']).strip()
                nome_cli = str(row.get('Nome', 'CLIENTE')).strip()
                tel_cli = limpar_numero(row.get('Telefone', ''))
                pacote_cli = str(row.get('Pacote', 'SEM ID')).strip()

                match_numero = re.search(r'(?:QUADRA|QD|Q|QR)\s*(\d+)', local_dump, re.IGNORECASE)
                match_cep = re.search(r'(\d{5})[-.\s]?(\d{3})', cep_dump)

                if match_numero and match_cep:
                    numero = str(int(match_numero.group(1)))
                    cep_prefixo = match_cep.group(1)
                    cep_sufixo = int(match_cep.group(2))

                    if cep_prefixo in ['72853', '72856']:
                        padrao_bairro = r'p[\.\s]*i*x+'
                        nome_bairro_amigavel = "Parque 9 ou 10"
                    elif cep_prefixo == '72859':
                        if cep_sufixo <= 500:
                            padrao_bairro = r'(p[\.\s]*8|p[\.\s]*v\s*i{3})'
                            nome_bairro_amigavel = "Mansões Parque 8"
                        else:
                            padrao_bairro = r'(p[\.\s]*7|p[\.\s]*v\s*i{2})'
                            nome_bairro_amigavel = "Mansões Parque 7"
                    else:
                        alertas_cep_invalido.append(f"{local_dump} - CEP: {cep_dump}")
                        continue

                    regex_busca_banco = rf'^Q\s*0*{numero}\s+{padrao_bairro}$'
                    chave_encontrada = ""
                    for chave_banco in banco_total.keys():
                        if re.match(regex_busca_banco, chave_banco, re.IGNORECASE):
                            chave_encontrada = chave_banco
                            break

                    if chave_encontrada:
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
                    salvar_progresso()
                    st.rerun()

            if alertas_nao_encontrado or alertas_sem_numero or alertas_cep_invalido:
                st.warning("⚠️ Alguns endereços não puderam ser mapeados:")
                for a in alertas_nao_encontrado:
                    st.write(f"- {a}")
                for a in alertas_sem_numero:
                    st.write(f"- {a}")
                for a in alertas_cep_invalido:
                    st.write(f"- {a}")

pendentes_total = [p for p in st.session_state.lista_pacotes if p['id'] not in st.session_state.entregues_id]
proximo_id = None
if st.session_state.ultima_pos and pendentes_total:
    dist_min = float('inf')
    for p in pendentes_total:
        coords = banco_total.get(p['nome'], (0, 0))
        d = math.sqrt((st.session_state.ultima_pos[0] - coords[0])**2 + (st.session_state.ultima_pos[1] - coords[1])**2)
        if d < dist_min:
            dist_min = d
            proximo_id = p['id']

agrupado = {}
for p in st.session_state.lista_pacotes:
    nome = p['nome']
    if nome not in agrupado:
        agrupado[nome] = {"total": 0, "pendentes": [], "concluidos": []}
    agrupado[nome]["total"] += 1
    if p['id'] in st.session_state.entregues_id:
        agrupado[nome]["concluidos"].append(p)
    else:
        agrupado[nome]["pendentes"].append(p)

pontos_js = []
for nome, info in agrupado.items():
    coords = banco_total.get(nome, (0, 0))
    pendentes_lista = info["pendentes"]
    concluidos_lista = info["concluidos"]
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

    lista_wpp = []
    for p_info in pendentes_lista:
        lista_wpp.append({
            "id_pacote": p_info['id'],
            "cliente": p_info.get("cliente", "Adicionado Manualmente"),
            "telefone": p_info.get("telefone", ""),
            "pacote": p_info.get("pacote", "Manual"),
            "quadra_real": p_info.get("quadra_original", nome),
            "concluido": False
        })

    lista_done = []
    for p_info in concluidos_lista:
        lista_done.append({
            "id_pacote": p_info['id'],
            "cliente": p_info.get("cliente", "Adicionado Manualmente"),
            "telefone": p_info.get("telefone", ""),
            "pacote": p_info.get("pacote", "Manual"),
            "quadra_real": p_info.get("quadra_original", nome),
            "concluido": True
        })

    pontos_js.append({
        "id": p_ids[0] if not esta_concluido else "done",
        "lat": coords[0],
        "lng": coords[1],
        "nome": nome,
        "restantes": len(p_ids),
        "total": info["total"],
        "concluidos_count": len(concluidos_lista),
        "concluido": esta_concluido,
        "cor": cor,
        "txt": display_txt,
        "lista_wpp": lista_wpp,
        "lista_done": lista_done,
        "is_next": any(pid == proximo_id for pid in p_ids)
    })

bolinhas_pendentes = len([p for p in pontos_js if not p['concluido']])
concluidos_total = len(st.session_state.entregues_id)
lista_opcoes_html = "".join([f'<option value="{n}">' for n in banco_total.keys()])
centro = st.session_state.map_center if st.session_state.map_center else (st.session_state.ultima_pos if st.session_state.ultima_pos else DEFAULT_CENTER)
zoom = st.session_state.map_zoom if st.session_state.map_zoom else DEFAULT_ZOOM

mapa_html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
body {{ margin: 0; padding: 0; font-family: system-ui, sans-serif; overflow: hidden; background: #0b0d10; }}
#map {{ height: 100vh; width: 100vw; z-index: 1; }}
.search-container {{ position: fixed; top: 10px; left: 10px; right: 10px; z-index: 1200; background: rgba(255,255,255,0.98); padding: 8px; border-radius: 14px; box-shadow: 0 8px 24px rgba(0,0,0,.18); }}
.search-row {{ display:flex; gap:6px; }}
#input-busca {{ flex:1; border:1px solid #d6d9de; padding:14px 12px; border-radius:10px; font-size:16px; outline:none; }}
.btn-add, .btn-confirm {{ border:none; border-radius:10px; font-weight:700; }}
.btn-add {{ background:#0b7cff; color:#fff; padding:0 18px; font-size:20px; }}
.btn-confirm {{ display:none; width:100%; background:#18a34a; color:#fff; padding:12px; margin-top:8px; }}
#batch-list {{ display:none; flex-wrap:wrap; gap:6px; margin-top:8px; padding-top:8px; border-top:1px solid #eceef2; }}
.batch-item {{ background:#f3f7ff; padding:5px 10px; border-radius:999px; font-size:12px; display:flex; align-items:center; gap:6px; border:1px solid #c7dcff; }}
.batch-item b {{ color:#d33; cursor:pointer; }}
.top-stats {{ position: fixed; top: 87px; left: 10px; right: 10px; display:flex; gap:8px; z-index:1100; }}
.badge {{ background: rgba(18,18,18,.88); color: #fff; padding: 8px 12px; border-radius: 999px; font-size: 13px; font-weight: 700; box-shadow: 0 6px 18px rgba(0,0,0,.18); }}
.badge.green {{ background: rgba(24,163,74,.92); }}
.btn-clear {{ position: fixed; top: 87px; right: 10px; z-index:1101; background: rgba(255,255,255,.96); border:none; padding:10px 14px; border-radius:12px; font-size:13px; font-weight:700; color:#d33; box-shadow:0 6px 18px rgba(0,0,0,.18); }}
#sheet {{ position: fixed; bottom: -100%; left: 0; right: 0; background: #111418; color: white; z-index: 2000; padding: 18px; border-radius: 20px 20px 0 0; box-shadow: 0 -5px 25px rgba(0,0,0,.45); transition: bottom .25s ease; max-height: 86vh; display:flex; flex-direction:column; }}
#sheet.active {{ bottom: 0; }}
.sheet-head {{ display:flex; align-items:flex-start; justify-content:space-between; gap:10px; margin-bottom:10px; }}
.s-header {{ font-size: 20px; font-weight: 800; }}
.s-sub {{ font-size: 13px; color: #9ca3af; margin-top: 4px; }}
.quick-actions {{ display:flex; gap:8px; flex-wrap:wrap; margin: 8px 0 12px; }}
.quick-btn {{ background:#1d4ed8; color:#fff; text-decoration:none; padding:10px 12px; border-radius:10px; font-weight:700; font-size:13px; }}
.quick-btn.secondary {{ background:#1f2937; }}
.quick-btn.success {{ background:#159947; }}
#tabs {{ display:flex; gap:8px; margin-bottom:12px; }}
.tab-btn {{ flex:1; background:#1c2128; color:#cfd6de; border:none; padding:12px 10px; border-radius:10px; font-weight:700; font-size:13px; }}
.tab-btn.active {{ background:#0b7cff; color:#fff; }}
.tab-panel {{ display:none; overflow-y:auto; flex:1; padding-right:4px; }}
.tab-panel.active {{ display:block; }}
.client-card {{ background:#1b2027; border:1px solid #2a313b; padding:12px; border-radius:12px; margin-bottom:12px; }}
.client-card.done {{ background:#132319; border-color:#235331; }}
.client-name {{ color:#7cc0ff; font-size:15px; font-weight:800; margin-bottom:4px; }}
.client-pkg {{ color:#95a2b2; font-size:12px; margin-bottom:10px; font-family:monospace; }}
.client-actions-row {{ display:flex; gap:8px; margin-bottom:8px; }}
.client-link {{ flex:1; text-align:center; text-decoration:none; padding:10px 8px; border-radius:10px; font-size:12px; font-weight:800; }}
.client-link.zap {{ background:#08140b; color:#25d366; border:1px solid #25d366; }}
.client-link.arrive {{ background:#16a34a; color:#fff; }}
.client-link.route {{ display:block; text-align:center; background:#222831; color:#fff; text-decoration:none; padding:10px 8px; border-radius:10px; font-size:12px; font-weight:800; }}
.client-link.undo {{ display:block; text-align:center; background:#f59e0b; color:#111; text-decoration:none; padding:10px 8px; border-radius:10px; font-size:12px; font-weight:800; }}
.client-link.donebtn {{ display:block; text-align:center; background:#22c55e; color:#fff; text-decoration:none; padding:11px 8px; border-radius:10px; font-size:13px; font-weight:900; margin-top:8px; }}
.pin {{ min-width: 40px; height: 40px; padding: 0 9px; border-radius: 999px; display:flex; align-items:center; justify-content:center; color:white; font-weight:900; border:2px solid white; font-size:13px; box-shadow:0 3px 10px rgba(0,0,0,.28); white-space:nowrap; }}
.leaflet-marker-icon.marker-hidden, .leaflet-marker-shadow.marker-hidden {{ opacity: 0 !important; transform: scale(.35) !important; transition: all .18s ease; pointer-events:none; }}
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
<div class="top-stats">
  <div class="badge">📍 {bolinhas_pendentes} pendentes</div>
  <div class="badge green">✅ {concluidos_total} concluídos</div>
</div>
<button class="btn-clear" onclick="if(confirm('Limpar todas as entregas do mapa?')) navigateWithMap('?limpar=1')">🗑️ LIMPAR</button>
<div id="map"></div>
<div id="sheet">
  <div class="sheet-head">
    <div>
      <div class="s-header" id="s-nome">Local</div>
      <div class="s-sub" id="s-info"></div>
    </div>
    <button onclick="closeSheet()" style="background:#1f2937;color:#fff;border:none;border-radius:10px;padding:10px 12px;font-weight:800;">Fechar</button>
  </div>
  <div class="quick-actions">
    <a id="s-gps" href="#" target="_blank" class="quick-btn">🧭 Abrir Google Maps</a>
    <button class="quick-btn secondary" onclick="openTab('pendentes')">Pendentes</button>
    <button class="quick-btn success" onclick="openTab('concluidos')">Concluídos</button>
  </div>
  <div id="tabs">
    <button id="tabbtn-pendentes" class="tab-btn active" onclick="openTab('pendentes')">Pendentes</button>
    <button id="tabbtn-concluidos" class="tab-btn" onclick="openTab('concluidos')">Concluídos</button>
  </div>
  <div id="panel-pendentes" class="tab-panel active"></div>
  <div id="panel-concluidos" class="tab-panel"></div>
</div>
<script>
const pontos = {json.dumps(pontos_js)};
const map = L.map('map', {{ zoomControl: false, attributionControl: false }}).setView([{centro[0]}, {centro[1]}], {zoom});
L.tileLayer('https://mt1.google.com/vt/lyrs=m&x={{x}}&y={{y}}&z={{z}}').addTo(map);
setTimeout(function() {{ map.invalidateSize(); }}, 500);

let queue = [];
const markerByPackage = {{}};
const pointByName = {{}};
pontos.forEach(p => pointByName[p.nome] = p);
function currentMapState() {{
  const c = map.getCenter();
  return `map_lat=${{c.lat}}&map_lng=${{c.lng}}&map_zoom=${{map.getZoom()}}`;
}}
function navigateWithMap(baseQuery) {{
  const glue = baseQuery.includes('?') ? '&' : '?';
  window.location.href = baseQuery + glue + currentMapState();
}}
function openTab(tab) {{
  document.getElementById('panel-pendentes').classList.toggle('active', tab === 'pendentes');
  document.getElementById('panel-concluidos').classList.toggle('active', tab === 'concluidos');
  document.getElementById('tabbtn-pendentes').classList.toggle('active', tab === 'pendentes');
  document.getElementById('tabbtn-concluidos').classList.toggle('active', tab === 'concluidos');
}}
function addToQueue() {{
  const input = document.getElementById('input-busca');
  const val = input.value.trim();
  if (val) {{ queue.push(val); renderQueue(); input.value=''; input.focus(); }}
}}
function removeFromQueue(idx) {{ queue.splice(idx, 1); renderQueue(); }}
function renderQueue() {{
  const container = document.getElementById('batch-list');
  const btn = document.getElementById('btn-confirm-all');
  if (queue.length > 0) {{
    container.style.display = 'flex';
    btn.style.display = 'block';
    container.innerHTML = queue.map((item, i) => '<div class="batch-item">'+item+'<b onclick="removeFromQueue('+i+')">✕</b></div>').join('');
  }} else {{
    container.style.display = 'none';
    btn.style.display = 'none';
  }}
}}
function sendBatch() {{
  if (queue.length > 0) {{
    const param = queue.map(encodeURIComponent).join('|');
    navigateWithMap('?add_batch=' + param);
  }}
}}
function closeSheet() {{ document.getElementById('sheet').classList.remove('active'); }}
function hidePackageMarker(idPacote) {{
  const marker = markerByPackage[idPacote];
  if (marker && marker._icon) marker._icon.classList.add('marker-hidden');
}}
function clientCardHtml(cli, isDone) {{
  const nome = (cli.cliente || 'Cliente').toUpperCase();
  const primeiroNome = (cli.cliente || 'Cliente').split(' ')[0] || 'Cliente';
  let html = '<div class="client-card'+(isDone ? ' done' : '')+'">';
  html += '<div class="client-name">👤 ' + nome + '</div>';
  html += '<div class="client-pkg">📦 Pacote: ' + (cli.pacote || 'Manual') + '</div>';
  if (!isDone) {{
    if (cli.telefone && cli.cliente !== 'Adicionado Manualmente') {{
      const msgChegando = encodeURIComponent('Olá ' + primeiroNome + ', Estou chegando no seu endereço (' + cli.quadra_real + '). Tem alguém pra receber a entrega agora?');
      const msgRota = encodeURIComponent('Oi ' + primeiroNome + ', Seu pacote para a *' + cli.quadra_real + '* está na rota de hoje. Passo até às 17h Ok?');
      html += '<div class="client-actions-row">';
      html += '<a href="https://wa.me/' + cli.telefone + '" target="_blank" class="client-link zap">💬 ZAP</a>';
      html += '<a href="https://wa.me/' + cli.telefone + '?text=' + msgChegando + '" target="_blank" class="client-link arrive">🚀 CHEGANDO</a>';
      html += '</div>';
      html += '<a href="https://wa.me/' + cli.telefone + '?text=' + msgRota + '" target="_blank" class="client-link route">📅 AVISAR ROTA</a>';
    }} else if (cli.cliente !== 'Adicionado Manualmente') {{
      html += '<div style="color:#f87171;font-size:12px;margin-bottom:8px;">⚠️ Sem número de telefone no sistema</div>';
    }}
    html += '<a href="#" onclick="concluirEntrega(\\'' + cli.id_pacote + '\\');return false;" class="client-link donebtn">✅ CONCLUIR ENTREGA</a>';
  }} else {{
    html += '<a href="#" onclick="desfazerEntrega(\\'' + cli.id_pacote + '\\');return false;" class="client-link undo">↩️ DESFAZER</a>';
  }}
  html += '</div>';
  return html;
}}
function renderSheet(point) {{
  document.getElementById('s-nome').innerText = point.nome;
  const txt = point.concluido
    ? 'Todas as entregas concluídas neste local'
    : `${{point.restantes}} pendente(s), ${{point.concluidos_count}} concluída(s), ${{point.total}} no total` + (point.is_next ? ' • próxima sugerida' : '');
  document.getElementById('s-info').innerText = txt;
  document.getElementById('s-gps').href = 'https://www.google.com/maps/dir/?api=1&destination=' + point.lat + ',' + point.lng;
  const pend = document.getElementById('panel-pendentes');
  const done = document.getElementById('panel-concluidos');
  pend.innerHTML = point.lista_wpp && point.lista_wpp.length ? point.lista_wpp.map(cli => clientCardHtml(cli, false)).join('') : '<div class="client-card"><div class="client-name">Nenhum pendente</div></div>';
  done.innerHTML = point.lista_done && point.lista_done.length ? point.lista_done.map(cli => clientCardHtml(cli, true)).join('') : '<div class="client-card done"><div class="client-name">Nenhuma concluída ainda</div></div>';
  openTab(point.lista_wpp && point.lista_wpp.length ? 'pendentes' : 'concluidos');
  document.getElementById('sheet').classList.add('active');
  map.panTo([point.lat, point.lng]);
}}
function concluirEntrega(idPacote) {{
  hidePackageMarker(idPacote);
  navigateWithMap('?concluir=' + encodeURIComponent(idPacote));
}}
function desfazerEntrega(idPacote) {{
  navigateWithMap('?desfazer=' + encodeURIComponent(idPacote));
}}
pontos.forEach(function(p) {{
  const icon = L.divIcon({{
    className: '',
    html: '<div class="pin" style="background:'+p.cor+'; opacity:'+(p.concluido ? 0.72 : 1)+'">'+p.txt+'</div>',
    iconSize: [null, 40], iconAnchor: [20, 20]
  }});
  const marker = L.marker([p.lat, p.lng], {{icon: icon}});
  marker.on('click', function(e) {{ L.DomEvent.stopPropagation(e); renderSheet(p); }});
  marker.addTo(map);
  (p.lista_wpp || []).forEach(cli => markerByPackage[cli.id_pacote] = marker);
}});
map.on('click', closeSheet);
map.locate({{watch: true, enableHighAccuracy: true}});
let userMarker;
map.on('locationfound', function(e) {{
  if (!userMarker) userMarker = L.circleMarker(e.latlng, {{radius: 8, color:'white', fillColor:'#4285F4', fillOpacity:1, weight:3}}).addTo(map);
  else userMarker.setLatLng(e.latlng);
}});
</script>
</body>
</html>
"""

components.html(mapa_html, height=900)