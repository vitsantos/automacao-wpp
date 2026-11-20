import csv
import os
import random
import re
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

# --- CONFIGURAÇÕES ---
USER_DATA_DIR = os.path.abspath("./sessao_wpp_edge")
ARQUIVO_CSV = "contatos_salvos.csv"
TEMPO_SINCRONIZACAO_INICIAL = 15  # segundos para o WhatsApp carregar conversas antigas
MAX_ROLAGENS = 150                # limite máximo de rolagens na lista
LIMITE_POR_EXECUCAO = 40          # encerra automaticamente após salvar essa quantidade


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


def rodar_automacao():
    numeros_processados = carregar_ja_salvos()
    print(f"Contatos já registrados no CSV anteriormente: {len(numeros_processados)}")
    print(f"Limite configurado para esta execução: {LIMITE_POR_EXECUCAO} contatos")

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
        print("Acessando https://web.whatsapp.com ...")
        page.goto("https://web.whatsapp.com/", wait_until="domcontentloaded")

        print("Aguardando WhatsApp Web carregar...")
        page.wait_for_selector('#pane-side', timeout=120000)

        print(f"Aguardando {TEMPO_SINCRONIZACAO_INICIAL}s para sincronização completa da lista...")
        time.sleep(TEMPO_SINCRONIZACAO_INICIAL)

        lista = page.locator('#pane-side')
        scroll_anterior = -1
        tentativas_sem_novas_conversas = 0
        novos_salvos_nessa_execucao = 0
        limite_atingido = False

        for rodada in range(MAX_ROLAGENS):
            if limite_atingido:
                break

            conversas = page.locator('#pane-side div[role="row"], #pane-side div[role="listitem"]').all()
            print(f"\n[Rodada {rodada + 1}] Conversas visíveis na tela: {len(conversas)}")

            for chat in conversas:
                if novos_salvos_nessa_execucao >= LIMITE_POR_EXECUCAO:
                    limite_atingido = True
                    print(f"\n[LIMITE] Meta de {LIMITE_POR_EXECUCAO} contatos atingida! Encerrando turno com segurança...")
                    break

                try:
                    # Localiza o título da conversa pelo test_id oficial
                    titulo_el = chat.get_by_test_id("cell-frame-title").locator("span[title]").first
                    if titulo_el.count() == 0:
                        titulo_el = chat.locator("span[title]").first
                    if titulo_el.count() == 0:
                        continue

                    titulo = titulo_el.get_attribute("title")

                    if not eh_numero_nao_salvo(titulo):
                        continue

                    if titulo in numeros_processados:
                        continue

                    numeros_processados.add(titulo)
                    print(f"--- Novo número encontrado: {titulo} ---")

                    # 1. Abre a conversa
                    chat.click()
                    pausa_humana(1.2, 2.2)

                    # 2. Abre 'Dados do contato'
                    page.get_by_test_id("conversation-info-header-button").click()
                    pausa_humana(1.2, 2.2)

                    # 3. Extrai o nome público (~Nome) no painel direito antes de abrir o formulário
                    painel_direito = page.locator("section").last
                    texto_painel = painel_direito.inner_text()

                    nome_wpp = ""
                    for linha in texto_painel.split("\n"):
                        if linha.startswith("~"):
                            nome_wpp = linha.replace("~", "").strip()
                            break

                    nome_final = f"{nome_wpp} Cliente" if nome_wpp else "Contato Cliente"
                    print(f"Salvando como: {nome_final}")

                    # 4. Clica exatamente no botão 'Adicionar' (evita 'Adicionar à lista')
                    btn_adicionar = page.get_by_role("button", name="Adicionar", exact=True)
                    if btn_adicionar.count() > 0 and btn_adicionar.first.is_visible():
                        btn_adicionar.first.click()
                        pausa_humana(1.0, 1.8)

                        # 5. Preenche o campo de Nome
                        campo_nome = page.get_by_test_id("contact-first-name-input")
                        campo_nome.wait_for(state="visible", timeout=5000)
                        campo_nome.click()
                        campo_nome.fill(nome_final)
                        pausa_humana(0.6, 1.2)

                        # 6. Garante que 'Sincronizar contato com' esteja ativado para refletir no iPhone
                        switch_sync = page.get_by_role("switch", name="Sincronizar contato com")
                        if switch_sync.count() > 0 and not switch_sync.is_checked():
                            switch_sync.check()
                            pausa_humana(0.5, 1.0)

                        # 7. Clica diretamente no botão oficial de salvar contato (ic-check)
                        btn_salvar = page.get_by_test_id("save-contact-btn")
                        btn_salvar.wait_for(state="visible", timeout=5000)
                        btn_salvar.click()
                        pausa_humana(1.0, 1.5)

                        # Registra no relatório CSV
                        registrar_csv(titulo, nome_wpp, nome_final)
                        novos_salvos_nessa_execucao += 1
                        print(f"[OK] {titulo} salvo como '{nome_final}' ({novos_salvos_nessa_execucao}/{LIMITE_POR_EXECUCAO})")
                        pausa_humana(2.5, 4.5)
                    else:
                        print(f"[AVISO] Botão 'Adicionar' não visível para {titulo} (pode ser grupo ou conta comercial).")

                except Exception as e:
                    print(f"[ERRO] Falha em conversa: {e}")
                    continue

            if limite_atingido:
                break

            # Rola suavemente (350px) para carregar o próximo bloco sem pular conversas
            lista.hover()
            page.mouse.wheel(0, 350)
            pausa_humana(4.5, 6.5)

            # Verifica se o scroll realmente desceu ou se chegou ao fim da lista
            scroll_atual = lista.evaluate("el => el.scrollTop")
            if scroll_atual == scroll_anterior:
                tentativas_sem_novas_conversas += 1
                print(f"Aguardando carregamento de mais conversas ({tentativas_sem_novas_conversas}/3)...")
                time.sleep(5)
                if tentativas_sem_novas_conversas >= 3:
                    print("Fim da lista de conversas alcançado!")
                    break
            else:
                tentativas_sem_novas_conversas = 0
                scroll_anterior = scroll_atual

        print(f"\nExecução finalizada! {novos_salvos_nessa_execucao} novos contatos salvos em '{ARQUIVO_CSV}'.")
        browser.close()


if __name__ == "__main__":
    rodar_automacao()