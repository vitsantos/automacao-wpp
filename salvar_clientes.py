import csv
import logging
import os
import random
import re
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

# Garante que os arquivos sejam salvos na pasta do script mesmo quando chamado pelo Windows
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DATA_DIR = os.path.join(BASE_DIR, "sessao_wpp_edge")
ARQUIVO_CSV = os.path.join(BASE_DIR, "contatos_salvos.csv")
ARQUIVO_LOG = os.path.join(BASE_DIR, "execucao_diaria.log")

# --- CONFIGURAÇÕES DA ROTINA DIÁRIA ---
TEMPO_SINCRONIZACAO_INICIAL = 20  # segundos para baixar mensagens do dia
MAX_ROLAGENS_DIARIAS = 25         # rolagens suficientes para cobrir conversas recentes
LIMITE_DIARIO = 50                # teto diário de segurança

logging.basicConfig(
    filename=ARQUIVO_LOG,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)


def log_info(msg):
    print(msg)
    logging.info(msg)


def pausa_humana(min_s=1.8, max_s=3.8):
    time.sleep(random.uniform(min_s, max_s))


def carregar_ja_salvos():
    salvos = set()
    if os.path.isfile(ARQUIVO_CSV):
        with open(ARQUIVO_CSV, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                if row.get("Numero"):
                    salvos.add(row["Numero"].strip())
    return salvos


def registrar_csv(numero, nome_original, nome_salvo):
    arquivo_existe = os.path.isfile(ARQUIVO_CSV)
    with open(ARQUIVO_CSV, mode="a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        if not arquivo_existe:
            writer.writerow(["Data/Hora", "Numero", "Nome Original WPP", "Nome Salvo"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            numero,
            nome_original if nome_original else "(Sem nome)",
            nome_salvo
        ])


def eh_numero_nao_salvo(texto):
    if not texto:
        return False
    texto = texto.strip()
    apenas_digitos = re.sub(r"\D", "", texto)
    if len(apenas_digitos) < 8:
        return False
    return bool(re.match(r"^[\+\(\d][\d\s\-\(\)]+$", texto))


def extrair_titulo_chat(chat):
    titulo_el = chat.get_by_test_id("cell-frame-title").locator("span[title]").first
    if titulo_el.count() == 0:
        titulo_el = chat.locator("span[title]").first
    if titulo_el.count() == 0:
        return None
    return titulo_el.get_attribute("title")


def processar_conversa(page, chat, titulo):
    log_info(f"Novo número encontrado: {titulo}")

    chat.click()
    pausa_humana(1.2, 2.2)

    page.get_by_test_id("conversation-info-header-button").click()
    pausa_humana(1.2, 2.2)

    painel_direito = page.locator("section").last
    texto_painel = painel_direito.inner_text()

    nome_wpp = ""
    for linha in texto_painel.split("\n"):
        if linha.startswith("~"):
            nome_wpp = linha.replace("~", "").strip()
            break

    nome_final = f"{nome_wpp} Cliente" if nome_wpp else "Contato Cliente"
    log_info(f"Salvando {titulo} como: {nome_final}")

    btn_adicionar = page.get_by_role("button", name="Adicionar", exact=True)
    if btn_adicionar.count() > 0 and btn_adicionar.first.is_visible():
        btn_adicionar.first.click()
        pausa_humana(1.0, 1.8)

        campo_nome = page.get_by_test_id("contact-first-name-input")
        campo_nome.wait_for(state="visible", timeout=5000)
        campo_nome.click()
        campo_nome.fill(nome_final)
        pausa_humana(0.6, 1.2)

        switch_sync = page.get_by_role("switch", name="Sincronizar contato com")
        if switch_sync.count() > 0 and not switch_sync.is_checked():
            switch_sync.check()
            pausa_humana(0.5, 1.0)

        btn_salvar = page.get_by_test_id("save-contact-btn")
        btn_salvar.wait_for(state="visible", timeout=5000)
        btn_salvar.click()
        pausa_humana(1.0, 1.5)

        registrar_csv(titulo, nome_wpp, nome_final)
        log_info(f"[OK] {titulo} salvo como '{nome_final}'.")
        pausa_humana(2.5, 4.5)
        return True

    log_info(f"[AVISO] Botão 'Adicionar' não visível para {titulo}.")
    return False


def rodar_rotina_diaria():
    log_info("=== INICIANDO EXECUÇÃO DIÁRIA AUTOMÁTICA ===")
    numeros_processados = carregar_ja_salvos()
    log_info(f"Contatos já registrados anteriormente: {len(numeros_processados)}")

    novos_salvos = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                channel="msedge",
                headless=False,
                no_viewport=True,
                args=[
                    "--start-maximized",
                    "--no-first-run",
                    "--no-default-browser-check"
                ]
            )

            page = browser.new_page()
            page.goto("https://web.whatsapp.com/", wait_until="domcontentloaded")
            page.wait_for_selector('#pane-side', timeout=120000)

            log_info(f"Aguardando {TEMPO_SINCRONIZACAO_INICIAL}s para sincronização...")
            time.sleep(TEMPO_SINCRONIZACAO_INICIAL)

            lista = page.locator('#pane-side')
            scroll_anterior = -1
            tentativas_fim = 0
            limite_atingido = False

            for rodada in range(MAX_ROLAGENS_DIARIAS):
                if limite_atingido:
                    break

                conversas = page.locator('#pane-side div[role="row"], #pane-side div[role="listitem"]').all()

                for chat in conversas:
                    if novos_salvos >= LIMITE_DIARIO:
                        limite_atingido = True
                        log_info(f"Limite diário de {LIMITE_DIARIO} contatos atingido.")
                        break

                    try:
                        titulo = extrair_titulo_chat(chat)
                        if not eh_numero_nao_salvo(titulo) or titulo in numeros_processados:
                            continue

                        numeros_processados.add(titulo)
                        if processar_conversa(page, chat, titulo):
                            novos_salvos += 1

                    except Exception as e:
                        log_info(f"[ERRO] Falha pontual em conversa: {e}")
                        continue

                if limite_atingido:
                    break

                lista.hover()
                page.mouse.wheel(0, 350)
                pausa_humana(4.0, 6.0)

                scroll_atual = lista.evaluate("el => el.scrollTop")
                if scroll_atual == scroll_anterior:
                    tentativas_fim += 1
                    if tentativas_fim >= 2:
                        break
                else:
                    tentativas_fim = 0
                    scroll_anterior = scroll_atual

            browser.close()

    except Exception as e:
        log_info(f"[ERRO CRÍTICO] Falha na rotina diária: {e}")

    log_info(f"=== EXECUÇÃO DIÁRIA FINALIZADA: {novos_salvos} novos contatos salvos ===\n")


if __name__ == "__main__":
    rodar_rotina_diaria()