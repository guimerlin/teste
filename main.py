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
DEFAULT_TEAM_ID = "0"


class FocalboardClient:
    def __init__(self, server_url):
        self.server_url = server_url.rstrip("/")
        self.api_url = f"{self.server_url}/api/v2"
        self.session = requests.Session()
        self.token = None

    def get_now_ms(self):
        return int(datetime.now().timestamp() * 1000)

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
        payload = {"type": "normal", "username": username, "password": password}

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
            else:
                print(f"Erro no login: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Erro de conexão: {e}")
        return False

    def get_boards(self, team_id=DEFAULT_TEAM_ID):
        """Busca boards de um time específico."""
        url = f"{self.api_url}/teams/{team_id}/boards"
        response = self.session.get(url)
        if response.status_code == 200:
            try:
                return response.json()
            except:
                return []
        return []

    def create_board_with_view(self, team_id, title):
        """Cria um board e uma view inicial usando o endpoint boards-and-blocks."""
        print(f"Criando novo board: {title}...")
        url = f"{self.api_url}/boards-and-blocks"
        board_id = str(uuid.uuid4()).replace("-", "")[:27]
        view_id = str(uuid.uuid4()).replace("-", "")[:27]
        now = self.get_now_ms()

        payload = {
            "boards": [
                {
                    "id": board_id,
                    "teamId": team_id,
                    "channelId": "",
                    "createdBy": "",
                    "modifiedBy": "",
                    "type": "P",
                    "minimumRole": "",
                    "title": title,
                    "description": "",
                    "icon": "",
                    "showDescription": False,
                    "isTemplate": False,
                    "templateVersion": 0,
                    "properties": {},
                    "cardProperties": [
                        {
                            "id": str(uuid.uuid4()).replace("-", "")[:27],
                            "name": "Status",
                            "type": "select",
                            "options": [],
                        }
                    ],
                    "createAt": now,
                    "updateAt": now,
                    "deleteAt": 0,
                }
            ],
            "blocks": [
                {
                    "id": view_id,
                    "parentId": board_id,
                    "boardId": board_id,
                    "schema": 1,
                    "type": "view",
                    "title": "Visualização de Quadro",
                    "fields": {
                        "viewType": "board",
                        "sortOptions": [],
                        "visiblePropertyIds": [],
                        "visibleOptionIds": [],
                        "hiddenOptionIds": [],
                    },
                    "createAt": now,
                    "updateAt": now,
                    "deleteAt": 0,
                }
            ],
        }

        response = self.session.post(url, json=payload)
        if response.status_code == 200:
            data = response.json()
            return data["boards"][0]
        else:
            print(f"Erro ao criar board: {response.text}")
            return None

    def create_card(self, board_id, title):
        url = f"{self.api_url}/boards/{board_id}/cards"
        card_id = str(uuid.uuid4()).replace("-", "")[:27]
        now = self.get_now_ms()
        payload = {
            "id": card_id,
            "boardId": board_id,
            "parentId": board_id,
            "title": title,
            "type": "card",
            "createAt": now,
            "updateAt": now,
            "deleteAt": 0,
        }
        response = self.session.post(url, json=payload)
        return response.json() if response.status_code == 200 else None

    def create_empty_block(self, board_id, card_id, block_type):
        url = f"{self.api_url}/boards/{board_id}/blocks"
        block_id = str(uuid.uuid4()).replace("-", "")[:27]
        now = self.get_now_ms()
        payload = [
            {
                "id": block_id,
                "boardId": board_id,
                "parentId": card_id,
                "type": block_type,
                "title": "",
                "fields": {},
                "schema": 1,
                "createAt": now,
                "updateAt": now,
                "deleteAt": 0,
            }
        ]
        response = self.session.post(url, json=payload)
        if response.status_code == 200:
            data = response.json()
            return data[0]["id"]
        return None

    def update_content_order(self, board_id, card_id, content_ids):
        url = f"{self.api_url}/boards/{board_id}/blocks/{card_id}"
        payload = {"updatedFields": {"contentOrder": content_ids}}
        response = self.session.patch(url, json=payload)
        return response.status_code == 200

    def update_block_title(self, board_id, block_id, title, fields=None):
        url = f"{self.api_url}/boards/{board_id}/blocks/{block_id}"
        payload = {"title": title, "updateAt": self.get_now_ms()}
        if fields:
            payload["fields"] = fields
        response = self.session.patch(url, json=payload)
        return response.status_code == 200


def main():
    client = FocalboardClient(SERVER_URL)
    if not client.login(USERNAME, PASSWORD):
        print("Falha na autenticação.")
        return

    # Buscar Boards do Time "0"
    print("\nBuscando boards...")
    all_boards = client.get_boards(DEFAULT_TEAM_ID)

    if not all_boards:
        print("Nenhum board encontrado no time '0'.")
        choice = 0
    else:
        print("\n--- Boards Disponíveis ---")
        for i, b in enumerate(all_boards):
            print(f"[{i}] {b.get('title', 'Sem Título')} (ID: {b.get('id')})")
        print(f"[{len(all_boards)}] -- CRIAR NOVO BOARD --")

        try:
            choice = int(input(f"\nEscolha o número do board (0-{len(all_boards)}): "))
        except ValueError:
            print("Escolha inválida.")
            return

    if choice == len(all_boards):
        new_title = input("Digite o nome do novo board: ")
        board = client.create_board_with_view(DEFAULT_TEAM_ID, new_title)
        if not board:
            print("Falha ao criar board.")
            return
        board_id = board["id"]
        board_name = board.get("title", "Novo Board")
    elif 0 <= choice < len(all_boards):
        board_id = all_boards[choice]["id"]
        board_name = all_boards[choice].get("title", "Selecionado")
    else:
        print("Opção fora do intervalo.")
        return

    # Carregar JSON
    try:
        with open("tasks.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Erro ao ler JSON: {e}")
        return

    tasks = data if isinstance(data, list) else [data]
    print(f"\nIniciando importação para o board: {board_name}...")

    for task_data in tasks:
        name = task_data.get("taskName", "Sem Nome")
        desc = task_data.get("description", "")
        checklist = task_data.get("checkList", [])

        print(f"Importando task: {name}...")
        card = client.create_card(board_id, name)
        if card:
            card_id = card["id"]
            current_content_order = []

            if desc:
                block_id = client.create_empty_block(board_id, card_id, "text")
                if block_id:
                    current_content_order.append(block_id)
                    client.update_content_order(
                        board_id, card_id, current_content_order
                    )
                    client.update_block_title(board_id, block_id, desc)

            if isinstance(checklist, list):
                for item in checklist:
                    item_text = (
                        item if isinstance(item, str) else item.get("text", "Item")
                    )
                    is_done = (
                        False if isinstance(item, str) else item.get("done", False)
                    )
                    block_id = client.create_empty_block(board_id, card_id, "checkbox")
                    if block_id:
                        current_content_order.append(block_id)
                        client.update_content_order(
                            board_id, card_id, current_content_order
                        )
                        fields = {"value": is_done}
                        client.update_block_title(board_id, block_id, item_text, fields)
        else:
            print(f"Falha ao criar card: {name}")

    print(f"\nSucesso! Tasks importadas no board: {board_name}")


if __name__ == "__main__":
    main()
