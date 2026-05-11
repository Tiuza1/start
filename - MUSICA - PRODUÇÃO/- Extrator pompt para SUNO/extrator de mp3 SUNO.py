import os
import threading
import shutil
import customtkinter as ctk
from tkinter import filedialog, messagebox
from google import genai

# Configuração visual do painel
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SunoAnalyzerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Suno AI - Audio Analyzer")
        self.geometry("750x650")
        self.caminho_mp3 = None

        self.label_titulo = ctk.CTkLabel(self, text="Gerador de Prompts para Suno AI", font=ctk.CTkFont(size=24, weight="bold"))
        self.label_titulo.pack(pady=(20, 10))

        self.frame_api = ctk.CTkFrame(self)
        self.frame_api.pack(pady=10, padx=20, fill="x")
        self.label_api = ctk.CTkLabel(self.frame_api, text="Google Gemini API Key:")
        self.label_api.pack(side="left", padx=10)
        self.entry_api = ctk.CTkEntry(self.frame_api, placeholder_text="Cole sua API Key aqui...", show="*", width=300)
        self.entry_api.pack(side="left", padx=10, fill="x", expand=True)

        self.frame_arquivo = ctk.CTkFrame(self)
        self.frame_arquivo.pack(pady=10, padx=20, fill="x")
        self.btn_selecionar = ctk.CTkButton(self.frame_arquivo, text="Caçar MP3", command=self.selecionar_arquivo, fg_color="#E07A5F", hover_color="#D16043")
        self.btn_selecionar.pack(side="left", padx=10, pady=10)
        self.label_arquivo = ctk.CTkLabel(self.frame_arquivo, text="Nenhum arquivo selecionado.")
        self.label_arquivo.pack(side="left", padx=10)

        self.btn_analisar = ctk.CTkButton(self, text="Analisar Áudio e Gerar Prompt", command=self.iniciar_analise, height=40, font=ctk.CTkFont(size=15, weight="bold"))
        self.btn_analisar.pack(pady=15)

        self.textbox_resultado = ctk.CTkTextbox(self, width=700, height=300, font=ctk.CTkFont(size=14))
        self.textbox_resultado.pack(pady=10, padx=20, fill="both", expand=True)
        self.textbox_resultado.insert("0.0", "O resultado aparecerá aqui...\n\n1. Insira sua API Key.\n2. Selecione seu MP3 local.\n3. Clique em Analisar.")
        
        self.btn_copiar = ctk.CTkButton(self, text="Copiar Prompt", command=self.copiar_texto, fg_color="#3D5A80", hover_color="#293241")
        self.btn_copiar.pack(pady=(5, 20))

    def selecionar_arquivo(self):
        caminho = filedialog.askopenfilename(filetypes=[("Arquivos de Áudio", "*.mp3 *.wav *.ogg *.m4a")])
        if caminho:
            self.caminho_mp3 = caminho
            nome_arquivo = os.path.basename(caminho)
            self.label_arquivo.configure(text=f"Selecionado: {nome_arquivo}")

    def iniciar_analise(self):
        api_key = self.entry_api.get().strip()
        if not api_key:
            messagebox.showwarning("Aviso", "Por favor, insira sua API Key do Gemini.")
            return
        if not self.caminho_mp3:
            messagebox.showwarning("Aviso", "Por favor, selecione um arquivo de áudio.")
            return

        self.btn_analisar.configure(state="disabled", text="Analisando... Isso pode levar 1 minuto")
        self.textbox_resultado.delete("0.0", "end")
        self.textbox_resultado.insert("0.0", "Fazendo upload e processando o áudio na IA... Aguarde.\n")

        threading.Thread(target=self.processar_audio, args=(api_key,), daemon=True).start()

    def processar_audio(self, api_key):
        arquivo_temp = None
        try:
            os.environ["GEMINI_API_KEY"] = api_key
            client = genai.Client()

            # Cria uma cópia com nome sem acentos/espaços para garantir que o upload funcione
            pasta = os.path.dirname(self.caminho_mp3)
            extensao = os.path.splitext(self.caminho_mp3)[1]
            arquivo_temp = os.path.join(pasta, f"temp_upload{extensao}")
            shutil.copy2(self.caminho_mp3, arquivo_temp)

            self.atualizar_texto("Fazendo upload do arquivo...\n")
            
            # Realiza o upload do arquivo renomeado
            audio_file = client.files.upload(file=arquivo_temp)

            self.atualizar_texto("Áudio enviado! Analisando batidas e arranjos...\n")

            prompt = """
            Você é um Produtor Musical experiente e Engenheiro de Som especialista no algoritmo do Suno AI.
            Sua missão é fazer a engenharia reversa das texturas, timbres e da harmonia deste áudio para criar um prompt extremamente técnico. Esqueça termos genéricos.
            
            Entregue no EXATO formato abaixo:

            1. STYLE PROMPT (Cerca de 150 caracteres, em inglês): 
            NÃO use palavras genéricas como "Trap" ou "Dark". Descreva a acústica!
            Use tags separadas por vírgula contendo:
            - Textura da bateria (ex: dry boom-bap snare, distorted 808 glides, crisp syncopated hi-hats).
            - Timbres/Instrumentos (ex: detuned analog synth, mellow rhodes piano, saturated bass).
            - Harmonia e Atmosfera (Traduza a progressão de acordes para sensações, ex: melancholic minor chord progression, tense unresolved melodies, ethereal reverb).
            - Mixagem (ex: heavy sidechain compression, vinyl crackle) e BPM exato.
            
            2. MORE OPTIONS:
            - Exclude styles: [Gêneros genéricos ou instrumentos que estragariam essa vibe]
            - Vocal Gender: [Male, Female, Both, ou N/A]
            - Weirdness: [0 a 100%]
            - Style Influence: [0 a 100%]

            3. LYRICS E STRUCTURE:
            Transcreva a letra com pontuação e acentuação corretas. 
            AQUI ESTÁ O SEGREDO: Em vez de Meta Tags simples, adicione as descrições dos instrumentos e da dinâmica dentro dos colchetes junto com a parte da música!
            Exemplos que você deve usar: 
            [Intro: detuned piano and vinyl crackle]
            [Verse: smooth vocal flow, deep sub-bass and crisp hi-hats]
            [Chorus: aggressive vocal delivery, wide synths, heavy kicks]
            [Beat Drop: sudden silence then massive 808 slide]
            Mapeie toda a dinâmica da música usando essa técnica.
            """

            resposta = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=[audio_file, prompt]
            )

            # Transforma a resposta em string ASCII segura para evitar crashes no painel
            texto_seguro = resposta.text
            self.atualizar_texto("\n=== RESULTADO PARA O SUNO AI ===\n\n" + texto_seguro)
            
            # Deleta do servidor
            client.files.delete(name=audio_file.name)

        except Exception as e:
            self.atualizar_texto(f"\n\nOcorreu um erro: {str(e)}")
        finally:
            if arquivo_temp and os.path.exists(arquivo_temp):
                try:
                    os.remove(arquivo_temp)
                except:
                    pass
            self.btn_analisar.configure(state="normal", text="Analisar Áudio e Gerar Prompt")

    def atualizar_texto(self, texto):
        self.textbox_resultado.insert("end", texto)
        self.textbox_resultado.see("end")

    def copiar_texto(self):
        texto = self.textbox_resultado.get("0.0", "end").strip()
        if texto:
            self.clipboard_clear()
            self.clipboard_append(texto)
            self.update() 
            self.btn_copiar.configure(text="Copiado!")
            self.after(2000, lambda: self.btn_copiar.configure(text="Copiar Prompt"))

if __name__ == "__main__":
    app = SunoAnalyzerApp()
    app.mainloop()