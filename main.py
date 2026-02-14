import json
import requests
import uuid
import time
import sys
from datetime import datetime

# Configurações do Servidor
SERVER_URL = "http://bandito.site:8000"
USERNAME = "luizbraga@live.com"
PASSWORD = "gui123321"
BOARDID = "bxkgso3obsirw9ef11ujk9e6qyr"


class FocalboardClient:
    def __init__(self, server_url):
        self.server_url = server_url.rstrip("/")
        self.api_url = f"{self.server_url}/api/v2"
        self.session = requests.Session()
        self.token = None

    def login(self, username, password):
        print(f"Efetuando login como {username}...")
        self.session.headers.update(
            {"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/json"}
        )

        try:
            self.session.get(f"{self.server_url}/")
            csrf_token = self.session.cookies.get("MMCSRF") or self.session.cookies.get(
                "focalboardSession"
            )
            if csrf_token:
                self.session.headers.update({"X-CSRF-Token": csrf_token})
        except Exception as e:
            print(f"Aviso ao acessar URL base: {e}")

        url = f"{self.api_url}/login"
        payloads = [{"type": "normal", "username": username, "password": password}]

        for i, payload in enumerate(payloads):
            try:
                response = self.session.post(url, json=payload)
                if response.status_code == 400 and "CSRF" in response.text:
                    csrf_token = self.session.cookies.get("MMCSRF")
                    if csrf_token:
                        self.session.headers.update({"X-CSRF-Token": csrf_token})
                        response = self.session.post(url, json=payload)

                if response.status_code == 200:
                    data = response.json()
                    self.token = data.get("token") or response.headers.get("Token")
                    if self.token:
                        self.session.headers.update(
                            {"Authorization": f"Bearer {self.token}"}
                        )
                        print("Login realizado com sucesso!")
                        return True
            except Exception as e:
                print(f"Erro de conexão: {e}")
        return False

    def get_teams(self):
        url = f"{self.api_url}/teams"
        response = self.session.get(url)
        return response.json() if response.status_code == 200 else []

    def create_board(self, team_id, title):
        print(f"Criando novo board: {title}...")
        url = f"{self.api_url}/boards"
        board_id = str(uuid.uuid4()).replace("-", "")[:27]
        payload = {
            "id": board_id,
            "teamId": team_id,
            "title": title,
            "type": "O",
            "minimumRole": "editor",
        }
        response = self.session.post(url, json=payload)
        return response.json() if response.status_code == 200 else None

    def create_card(self, board_id, title):
        url = f"{self.api_url}/boards/{board_id}/cards"
        card_id = str(uuid.uuid4()).replace("-", "")[:27]
        payload = {
            "id": card_id,
            "boardId": board_id,
            "parentId": board_id,
            "title": title,
            "type": "card",
        }
        response = self.session.post(url, json=payload)
        return response.json() if response.status_code == 200 else None

    def create_empty_block(self, board_id, card_id, block_type):
        """Passo 1: Cria um bloco vazio no servidor."""
        url = f"{self.api_url}/boards/{board_id}/blocks"
        block_id = str(uuid.uuid4()).replace("-", "")[:27]
        payload = [
            {
                "id": block_id,
                "boardId": board_id,
                "parentId": card_id,
                "type": block_type,
                "title": "",
                "fields": {},
                "schema": 1,
                "createAt": int(datetime.now().timestamp() * 1000),
                "updateAt": int(datetime.now().timestamp() * 1000),
            }
        ]
        response = self.session.post(url, json=payload)
        returnId = response.json()
        return returnId[0]["id"] if response.status_code == 200 else None

    def update_content_order(self, board_id, card_id, content_ids):
        """Passo 2: Atualiza a ordem de conteúdo no card pai."""
        url = f"{self.api_url}/boards/{board_id}/blocks/{card_id}"
        payload = {"updatedFields": {"contentOrder": content_ids}}
        response = self.session.patch(url, json=payload)
        return response.status_code == 200

    def update_block_title(self, board_id, block_id, title, fields=None):
        """Passo 3: Atualiza o título/conteúdo do bloco criado."""
        url = f"{self.api_url}/boards/{board_id}/blocks/{block_id}"
        payload = {"title": title}
        if fields:
            payload["fields"] = fields
        response = self.session.patch(url, json=payload)
        return response.status_code == 200


def main():
    client = FocalboardClient(SERVER_URL)
    if not client.login(USERNAME, PASSWORD):
        print("Falha na autenticação.")
        return

    try:
        with open("tasks.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Erro ao ler JSON: {e}")
        return

    tasks = data if isinstance(data, list) else [data]
    board_id = BOARDID
    board_name = "Imported Tasks"
    for task_data in tasks:
        name = task_data.get("taskName", "Sem Nome")
        desc = task_data.get("description", "")
        checklist = task_data.get("checkList", [])

        print(f"Importando task: {name}...")
        card = client.create_card(board_id, name)
        if card:
            card_id = card["id"]
            current_content_order = []

            # Fluxo para Descrição
            if desc:
                # 1. Criar bloco vazio
                block_id = client.create_empty_block(board_id, card_id, "text")
                if block_id:
                    current_content_order.append(block_id)
                    # 2. Atualizar ordem no card
                    client.update_content_order(
                        board_id, card_id, current_content_order
                    )
                    # 3. Atualizar conteúdo do bloco
                    client.update_block_title(board_id, block_id, desc)

            # Fluxo para Checklist
            if isinstance(checklist, list):
                for item in checklist:
                    item_text = (
                        item if isinstance(item, str) else item.get("text", "Item")
                    )
                    is_done = (
                        False if isinstance(item, str) else item.get("done", False)
                    )

                    # 1. Criar bloco vazio
                    block_id = client.create_empty_block(board_id, card_id, "checkbox")
                    if block_id:
                        current_content_order.append(block_id)
                        # 2. Atualizar ordem no card
                        client.update_content_order(
                            board_id, card_id, current_content_order
                        )
                        # 3. Atualizar conteúdo e status
                        fields = {"value": is_done}
                        client.update_block_title(board_id, block_id, item_text, fields)
        else:
            print(f"Falha ao criar card: {name}")

    print(
        f"\nSucesso! Tasks importadas seguindo o fluxo do navegador no board: {board_name}"
    )


if __name__ == "__main__":
    main()
