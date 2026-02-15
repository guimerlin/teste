import json
import requests
import time
import sys

# --- Configurações ---
PLANKA_URL = "http://bandito.site:3000/api"
USERNAME = "luizbraga@live.com"
PASSWORD = "gui123321"
JSON_FILE = "tasks.json"


class PlankaImporter:
    def __init__(self, url):
        self.url = url
        self.session = requests.Session()
        self.token = None
        self.label_cache = {}  # Cache para evitar recriar rótulos (Nome+Cor -> ID)

    def login(self):
        resp = self.session.post(
            f"{self.url}/access-tokens",
            json={"emailOrUsername": USERNAME, "password": PASSWORD},
        )
        if resp.ok:
            self.token = resp.json().get("item")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            return True
        return False

    # --- Funções Baseadas na Documentação ---

    def get_projects(self):
        resp = self.session.get(f"{self.url}/projects")
        return resp.json().get("items", []) if resp.ok else []

    def get_board_details(self, board_id):
        # Busca detalhes do board incluindo rótulos existentes
        resp = self.session.get(f"{self.url}/boards/{board_id}")
        return resp.json() if resp.ok else {}

    def create_list(self, board_id, name, position):
        payload = {"name": name, "position": position, "type": "active"}
        resp = self.session.post(f"{self.url}/boards/{board_id}/lists", json=payload)
        return resp.json().get("item")

    def create_card(self, list_id, task_data, position):
        payload = {
            "name": task_data.get("taskName"),
            "description": task_data.get("description"),
            "position": position,
            "type": "project",
        }
        resp = self.session.post(f"{self.url}/lists/{list_id}/cards", json=payload)
        return resp.json().get("item")

    def create_label(self, board_id, name, color, position=65536):
        payload = {"name": name, "color": color, "position": position}
        resp = self.session.post(f"{self.url}/boards/{board_id}/labels", json=payload)
        return resp.json().get("item") if resp.ok else None

    def add_label_to_card(self, card_id, label_id):
        payload = {"labelId": label_id}
        resp = self.session.post(
            f"{self.url}/cards/{card_id}/card-labels", json=payload
        )
        return resp.ok

    def create_task_list(self, card_id, name):
        payload = {"name": name, "position": 65536}
        resp = self.session.post(f"{self.url}/cards/{card_id}/task-lists", json=payload)
        return resp.json().get("item")

    def create_task(self, task_list_id, name, completed=False):
        payload = {
            "name": name,
            "isCompleted": completed,
            "position": 65536,
            "type": "task",
        }
        resp = self.session.post(
            f"{self.url}/task-lists/{task_list_id}/tasks", json=payload
        )
        return resp.ok


def main():
    api = PlankaImporter(PLANKA_URL)
    if not api.login():
        print("Falha no login.")
        return

    # Seleção de Projeto e Board
    projects = api.get_projects()
    for i, p in enumerate(projects):
        print(f"[{i}] {p['name']}")
    project = projects[int(input("Projeto: "))]

    # Extração de boards do included (conforme seu log)
    proj_resp = api.session.get(f"{api.url}/projects/{project['id']}").json()
    boards = proj_resp.get("included", {}).get("boards", [])
    for i, b in enumerate(boards):
        print(f"[{i}] {b['name']}")
    board = boards[int(input("Board: "))]

    # Mapear rótulos já existentes no Board para o Cache
    board_data = api.get_board_details(board["id"])
    existing_labels = board_data.get("included", {}).get("labels", [])
    for lab in existing_labels:
        key = f"{lab['name']}_{lab['color']}"
        api.label_cache[key] = lab["id"]

    # Carregar JSON
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        tasks_data = json.load(f)
        if not isinstance(tasks_data, list):
            tasks_data = [tasks_data]

    existing_lists = {}

    print(f"\nImportando para: {board['name']}")

    for idx, t in enumerate(tasks_data):
        cat = t.get("category", "Geral")
        if cat not in existing_lists:
            print(f"Lista: {cat}")
            new_l = api.create_list(board["id"], cat, (idx + 1) * 65536)
            if new_l:
                existing_lists[cat] = new_l["id"]
            else:
                continue

        # Criar Card
        print(f" -> Card: {t['taskName']}")
        card = api.create_card(existing_lists[cat], t, (idx + 1) * 65536)
        if not card:
            continue

        # --- Lógica de Rótulos (Flags) ---
        if "labels" in t:
            for lab_json in t["labels"]:
                l_name = lab_json["name"]
                l_color = lab_json.get("color", "morning-sky")
                cache_key = f"{l_name}_{l_color}"

                # Se o rótulo não existe no board, cria agora
                if cache_key not in api.label_cache:
                    print(f"    + Criando Rótulo: {l_name} ({l_color})")
                    new_lab = api.create_label(board["id"], l_name, l_color)
                    if new_lab:
                        api.label_cache[cache_key] = new_lab["id"]

                # Vincula o rótulo ao Card
                if cache_key in api.label_cache:
                    api.add_label_to_card(card["id"], api.label_cache[cache_key])

        # --- Lógica de Checklist ---
        if t.get("checkList"):
            tl = api.create_task_list(card["id"], "Checklist")
            if tl:
                for item in t["checkList"]:
                    api.create_task(tl["id"], item)

    print("\nImportação completa!")


if __name__ == "__main__":
    main()
