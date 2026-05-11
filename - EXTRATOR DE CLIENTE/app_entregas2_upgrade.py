import os
import json
import time
import threading
import queue
import ctypes

import cv2
import mss
import numpy as np
import pyautogui
import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText

CONFIG_FILE = 'config_ninja_buffs.json'
AURA_FILE = 'aura.jpg'
SKIN_FILE = 'troca_de_pele-2.jpg'
MATCH_THRESHOLD_AURA = 0.78
MATCH_THRESHOLD_SKIN = 0.78
SKIN_RECAST_COOLDOWN = 1.5
CAPS_DEBOUNCE = 0.30
POLL_INTERVAL = 0.02

log_q = queue.Queue()
log_window_started = False
root_ref = None


def log(msg):
    t = time.strftime('%H:%M:%S')
    log_q.put(f'[{t}] {msg}')


def carregar_template(path):
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(path)
    return img


def detectar_template(gray_img, template, threshold):
    if gray_img.shape[0] < template.shape[0] or gray_img.shape[1] < template.shape[1]:
        return False, 0.0
    res = cv2.matchTemplate(gray_img, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    return max_val >= threshold, float(max_val)


def esperar_tecla_espaco(mensagem):
    messagebox.showinfo('CalibraÃ§Ã£o', mensagem)
    log(mensagem.replace('\n', ' '))
    while True:
        if ctypes.windll.user32.GetAsyncKeyState(0x20) & 0x8000:
            while ctypes.windll.user32.GetAsyncKeyState(0x20) & 0x8000:
                time.sleep(0.03)
            x, y = pyautogui.position()
            log(f'Ponto capturado em x={x}, y={y}')
            time.sleep(0.2)
            return x, y
        time.sleep(0.02)


def calibrar_area():
    p1 = esperar_tecla_espaco('Passo 1/2: leve o mouse ao canto SUPERIOR ESQUERDO da Ã¡rea dos buffs e aperte ESPAÃ‡O.')
    p2 = esperar_tecla_espaco('Passo 2/2: leve o mouse ao canto INFERIOR DIREITO da Ã¡rea dos buffs e aperte ESPAÃ‡O.')
    left = min(p1[0], p2[0])
    top = min(p1[1], p2[1])
    width = abs(p2[0] - p1[0])
    height = abs(p2[1] - p1[1])
    cfg = {'top': top, 'left': left, 'width': width, 'height': height}
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    log(f"Ãrea salva: left={left} top={top} width={width} height={height}")
    messagebox.showinfo('CalibraÃ§Ã£o', 'Ãrea salva com sucesso.')
    return cfg


def escolher_area_inicial():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            resposta = messagebox.askyesnocancel(
                'Ãrea de buffs',
                'Sim = usar a Ãºltima Ã¡rea salva\n'
                'NÃ£o = redefinir a Ã¡rea agora\n'
                'Cancelar = fechar\n\n'
                f"left={cfg['left']} top={cfg['top']} width={cfg['width']} height={cfg['height']}"
            )
            if resposta is None:
                log('Abertura cancelada pelo usuÃ¡rio.')
                return None
            if resposta is True:
                log('Usando Ãºltima Ã¡rea salva.')
                return cfg
            log('UsuÃ¡rio escolheu redefinir a Ã¡rea.')
            return calibrar_area()
        except Exception as e:
            log(f'Falha ao ler config antiga: {e}')
            return calibrar_area()
    log('Nenhuma configuraÃ§Ã£o encontrada, iniciando calibraÃ§Ã£o.')
    return calibrar_area()


def enviar_comando(placa, comando):
    if not placa:
        log(f'Placa ausente: {comando} nÃ£o enviado')
        return False
    try:
        placa.write((comando + '\n').encode('utf-8'))
        placa.flush()
        log(f'Enviado -> {comando}')
        return True
    except Exception as e:
        log(f'Erro ao enviar {comando}: {e}')
        return False


def atualizar_logs_widget(txt, root):
    while not log_q.empty():
        txt.configure(state='normal')
        txt.insert(tk.END, log_q.get() + '\n')
        txt.see(tk.END)
        txt.configure(state='disabled')
    root.after(50, atualizar_logs_widget, txt, root)


def iniciar_janela_logs(stop_event, area_holder):
    global root_ref
    root = tk.Tk()
    root_ref = root
    root.title('Ninja Combo Monitor - Log')
    root.geometry('860x540')
    root.configure(bg='#111111')
    root.attributes('-topmost', True)

    top = tk.Frame(root, bg='#111111')
    top.pack(fill='x', padx=10, pady=(10, 0))

    lbl = tk.Label(top, text='Caps: Aura -> C_ATK | Sem Aura -> C_FULL | Troca de Pele ausente -> SKIN', bg='#111111', fg='#00ff88', font=('Consolas', 10, 'bold'))
    lbl.pack(side='left')

    def redefinir():
        root.attributes('-topmost', False)
        nova = calibrar_area()
        area_holder['value'] = nova
        root.attributes('-topmost', True)

    btn = tk.Button(top, text='Redefinir Ã¡rea', command=redefinir, bg='#222222', fg='white')
    btn.pack(side='right')

    txt = ScrolledText(root, bg='black', fg='#00ff88', insertbackground='white', font=('Consolas', 10))
    txt.pack(fill='both', expand=True, padx=10, pady=10)
    txt.configure(state='disabled')

    def on_close():
        stop_event.set()
        root.destroy()

    root.protocol('WM_DELETE_WINDOW', on_close)
    atualizar_logs_widget(txt, root)
    root.mainloop()


def garantir_janela_logs(stop_event, area_holder):
    global log_window_started
    if not log_window_started:
        log_window_started = True
        th = threading.Thread(target=iniciar_janela_logs, args=(stop_event, area_holder), daemon=True)
        th.start()
        time.sleep(0.6)


def executar(placa, stop_event):
    area_holder = {'value': None}
    garantir_janela_logs(stop_event, area_holder)

    log('Script iniciado pelo gerenciador.')
    log(f'Pasta atual: {os.getcwd()}')

    if not os.path.exists(AURA_FILE):
        log(f'ERRO: arquivo nÃ£o encontrado -> {AURA_FILE}')
        return
    if not os.path.exists(SKIN_FILE):
        log(f'ERRO: arquivo nÃ£o encontrado -> {SKIN_FILE}')
        return

    try:
        aura_tpl = carregar_template(AURA_FILE)
        skin_tpl = carregar_template(SKIN_FILE)
        log(f'Templates carregados: aura={aura_tpl.shape} pele={skin_tpl.shape}')
    except Exception as e:
        log(f'ERRO carregando templates: {e}')
        return

    if root_ref:
        root_ref.attributes('-topmost', False)
    area = escolher_area_inicial()
    if root_ref:
        root_ref.attributes('-topmost', True)

    if area is None:
        log('ExecuÃ§Ã£o cancelada antes de iniciar o loop.')
        return

    area_holder['value'] = area
    log(f"Ãrea ativa: left={area['left']} top={area['top']} width={area['width']} height={area['height']}")

    try:
        sct = mss.mss()
    except Exception as e:
        log(f'ERRO iniciando captura de tela: {e}')
        return

    estado_caps_anterior = ctypes.windll.user32.GetKeyState(0x14) & 1
    ultimo_caps = 0.0
    ultimo_skin = 0.0
    ultimo_log_status = 0.0

    log('Loop principal iniciado.')

    while not stop_event.is_set():
        try:
            area = area_holder['value']
            shot = np.array(sct.grab(area))
            gray = cv2.cvtColor(shot, cv2.COLOR_BGRA2GRAY)
            tem_aura, score_aura = detectar_template(gray, aura_tpl, MATCH_THRESHOLD_AURA)
            tem_skin, score_skin = detectar_template(gray, skin_tpl, MATCH_THRESHOLD_SKIN)
            agora = time.time()

            estado_caps_atual = ctypes.windll.user32.GetKeyState(0x14) & 1
            if estado_caps_atual != estado_caps_anterior and (agora - ultimo_caps) >= CAPS_DEBOUNCE:
                ultimo_caps = agora
                log(f'Caps mudou: {estado_caps_anterior} -> {estado_caps_atual}')
                if tem_aura:
                    log(f'Aura detectada ({score_aura:.2f}) -> C_ATK')
                    enviar_comando(placa, 'C_ATK')
                else:
                    log(f'Aura ausente ({score_aura:.2f}) -> C_FULL')
                    enviar_comando(placa, 'C_FULL')
            estado_caps_anterior = estado_caps_atual

            if not tem_skin and (agora - ultimo_skin) >= SKIN_RECAST_COOLDOWN:
                ultimo_skin = agora
                log(f'Troca de Pele ausente ({score_skin:.2f}) -> SKIN')
                enviar_comando(placa, 'SKIN')

            if agora - ultimo_log_status >= 2.0:
                ultimo_log_status = agora
                log(f'Status | Caps={estado_caps_atual} | Aura={tem_aura} ({score_aura:.2f}) | Pele={tem_skin} ({score_skin:.2f})')

        except Exception as e:
            log(f'ERRO no loop: {e}')
            time.sleep(0.2)

        time.sleep(POLL_INTERVAL)

    log('Loop finalizado pelo stop_event.')