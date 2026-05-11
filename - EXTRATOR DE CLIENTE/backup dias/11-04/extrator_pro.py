import os, subprocess, re, time
import xml.etree.cElementTree as ET
import csv
from datetime import datetime

# --- CONFIGURAÇÕES DE IDs ---
ID_CARD = 'com.jtexpress.braout:id/rl_parent'
ID_NOME = 'com.jtexpress.braout:id/tv_wait_name'
ID_BOTAO_TEL = 'com.jtexpress.braout:id/iv_wait_phone'
ID_PEDIDO = 'com.jtexpress.braout:id/tv_bill_code'
ID_ENDERECO = 'com.jtexpress.braout:id/tv_wait_adress'

ultimo_nome_salvo = ""
ultimo_numero_salvo = ""

def parse_bounds(bounds_str):
    nums = re.findall(r'\d+', bounds_str)
    x1, y1, x2, y2 = map(int, nums)
    return (x1 + x2) // 2, (y1 + y2) // 2

def extrair_local_inteligente(texto):
    if not texto: return "Endereço não lido"
    # Padrão para Quadra/QD/QR e número
    padrao = r'((?:QUADRA|QD|QR|Q|CONJUNTO|CJ|CONJ)\.?\s*\d+)'
    match = re.search(padrao, texto, re.IGNORECASE)
    if match:
        resultado = match.group(1).upper().strip()
        # Remove "QUADRA QUADRA" se houver duplicata
        resultado = re.sub(r'(QUADRA|QD|QR)\s+\1', r'\1', resultado)
        return resultado
    palavras = texto.split()
    # Limpa palavras curtas/pontos
    palavras = [p for p in palavras if len(p) > 1 or p.isalnum()]
    return " ".join(palavras[:3]) if len(palavras) > 0 else "Local não identificado"

def extrair_do_discador_puro():
    if os.path.exists("dialer.xml"): os.remove("dialer.xml")
    subprocess.run("adb shell uiautomator dump /sdcard/dialer.xml", shell=True, capture_output=True)
    subprocess.run("adb pull /sdcard/dialer.xml .", shell=True, capture_output=True)
    try:
        tree = ET.parse("dialer.xml")
        for n in tree.getroot().iter('node'):
            text = n.get('text')
            if text:
                limpo = re.sub(r'\D', '', text)
                if len(limpo) >= 8: return limpo
    except: pass
    return ""

def voltar_ao_app():
    subprocess.run("adb shell input keyevent 4", shell=True)
    time.sleep(0.5)
    subprocess.run("adb shell input keyevent 4", shell=True)
    time.sleep(1.2)

def rolar_tela_ajustado():
    print("[i] Scroll...")
    subprocess.run("adb shell input swipe 500 1100 500 550 700", shell=True)
    time.sleep(1.5)

def capturar_com_tentativas(x, y, nome_cliente):
    global ultimo_numero_salvo, ultimo_nome_salvo
    for tentativa in range(3):
        subprocess.run(f"adb shell input tap {x} {y}", shell=True)
        time.sleep(1.8)
        numero_atual = extrair_do_discador_puro()
        
        if numero_atual == "" or (numero_atual == ultimo_numero_salvo and nome_cliente != ultimo_nome_salvo):
            print(f"      [!] Erro de sincronismo para {nome_cliente}. Tentando de novo...")
            voltar_ao_app()
            time.sleep(1)
            continue
            
        ultimo_numero_salvo = numero_atual
        ultimo_nome_salvo = nome_cliente
        voltar_ao_app()
        return numero_atual
    return numero_atual if numero_atual != "" else "ERRO"

def rodar_extrator_v3_4():
    data_formatada = datetime.now().strftime("%d-%m-%Y")
    arquivo_csv = f"clientes_do_dia ({data_formatada}).csv"
    
    # --- NOVO: CAMPO PARA PULAR PACOTES ESPECÍFICOS ---
    print("\n" + "="*40)
    print("   CONFIGURAÇÃO DE INÍCIO")
    entrada_pular = input("Digite os IDs dos pacotes para PULAR (separe por virgula)\nou aperte ENTER para nenhum: ")
    # Transformamos em uma lista limpa de IDs
    lista_negra = [id.strip() for id in entrada_pular.split(",") if id.strip()]
    if lista_negra:
        print(f"[i] O robô irá ignorar {len(lista_negra)} pacotes específicos.")
    # --------------------------------------------------

    processados = set()
    if os.path.exists(arquivo_csv):
        with open(arquivo_csv, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) > 1: processados.add(row[1])

    print("\n" + "="*40)
    print(f"   EXTRATOR J&T V3.4 - {data_formatada}")
    print("="*40)

    try:
        while True:
            subprocess.run("adb shell uiautomator dump /sdcard/v.xml", shell=True, capture_output=True)
            subprocess.run("adb pull /sdcard/v.xml .", shell=True, capture_output=True)
            
            try:
                tree = ET.parse("v.xml")
                root = tree.getroot()
                cards = [n for n in root.iter('node') if n.get('resource-id') == ID_CARD]

                if not cards:
                    rolar_tela_ajustado()
                    continue

                for card in cards:
                    nome, id_pacote, tel_bounds, txt_endereco = None, None, None, ""
                    
                    for child in card.iter('node'):
                        rid = child.get('resource-id')
                        if rid == ID_NOME: nome = child.get('text')
                        elif rid == ID_PEDIDO: id_pacote = child.get('text')
                        elif rid == ID_BOTAO_TEL: tel_bounds = child.get('bounds')
                        elif rid == ID_ENDERECO: txt_endereco = child.get('text')

                    if nome and id_pacote and tel_bounds:
                        # --- VERIFICAÇÃO DE LISTA NEGRA ---
                        if id_pacote in lista_negra:
                            print(f"[!] IGNORADO (Manual): {nome} | ID: {id_pacote}")
                            processados.add(id_pacote)
                            continue
                        # ----------------------------------

                        if id_pacote not in processados:
                            local_identificado = extrair_local_inteligente(txt_endereco)
                            x, y = parse_bounds(tel_bounds)

                            print(f"[*] {nome} | {local_identificado}")
                            telefone = capturar_com_tentativas(x, y, nome)

                            with open(arquivo_csv, 'a', newline='', encoding='utf-8') as f:
                                writer = csv.writer(f)
                                if os.path.getsize(arquivo_csv) == 0:
                                    writer.writerow(["Nome", "Pacote", "Telefone", "Local"])
                                writer.writerow([nome, id_pacote, telefone, local_identificado])

                            processados.add(id_pacote)

                rolar_tela_ajustado()

            except Exception as e:
                print(f"Erro no processamento: {e}")
                time.sleep(2)
                rolar_tela_ajustado()

    except KeyboardInterrupt:
        print("\n[!] Finalizado.")

if __name__ == "__main__":
    rodar_extrator_v3_4()