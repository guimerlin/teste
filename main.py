import json
import requests
import time
import os

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
        self.label_cache = {}  # Cache de Rótulos (Nome_Cor -> ID)
        self.list_cache = {}  # Cache de Listas (Nome -> ID)

    def login(self):
        url = f"{self.url}/access-tokens"
        payload = {"emailOrUsername": USERNAME, "password": PASSWORD}
        resp = self.session.post(url, json=payload)
        if resp.ok:
            self.token = resp.json().get("item")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            return True
        return False

    def get_projects(self):
        resp = self.session.get(f"{self.url}/projects")
        return resp.json().get("items", []) if resp.ok else []

    def get_board_details(self, board_id):
        # Busca o board e seus componentes (listas e labels)
        resp = self.session.get(f"{self.url}/boards/{board_id}")
        return resp.json() if resp.ok else {}

    # --- Funções de Criação Baseadas na Documentação ---

    def create_list(self, board_id, name, position):
        url = f"{self.url}/boards/{board_id}/lists"
        payload = {
            "name": name[:128],
            "position": position,
            "type": "active",  # Obrigatório conforme logs anteriores
        }
        resp = self.session.post(url, json=payload)
        return resp.json().get("item") if resp.ok else None

    def create_card(self, list_id, task_data, position):
        url = f"{self.url}/lists/{list_id}/cards"
        payload = {
            "name": task_data.get("taskName")[:1024],
            "description": task_data.get("description"),
            "position": position,
            "type": "project",  # Obrigatório conforme whitelist do seu servidor
        }
        resp = self.session.post(url, json=payload)
        return resp.json().get("item") if resp.ok else None

    def create_label(self, board_id, name, color):
        url = f"{self.url}/boards/{board_id}/labels"
        payload = {"name": name, "color": color, "position": 65536}
        resp = self.session.post(url, json=payload)
        return resp.json().get("item") if resp.ok else None

    def add_label_to_card(self, card_id, label_id):
        url = f"{self.url}/cards/{card_id}/card-labels"
        self.session.post(url, json={"labelId": label_id})

    def create_checklist_structure(self, card_id, items):
        # Primeiro cria a Task List (Checklist)
        url_tl = f"{self.url}/cards/{card_id}/task-lists"
        resp_tl = self.session.post(
            url_tl, json={"name": "Checklist", "position": 65536}
        )

        if resp_tl.ok:
            tl_id = resp_tl.json().get("item", {}).get("id")
            for i, item_text in enumerate(items):
                url_task = f"{self.url}/task-lists/{tl_id}/tasks"
                payload = {
                    "name": item_text[:1024],
                    "position": (i + 1) * 65536,
                    "isCompleted": False,
                    "type": "task",
                }
                self.session.post(url_task, json=payload)


def main():
    importer = PlankaImporter(PLANKA_URL)
    if not importer.login():
        print("Erro: Falha na autenticação.")
        return

    # 1. Seleção de Projeto
    projects = importer.get_projects()
    for i, p in enumerate(projects):
        print(f"[{i}] {p['name']}")
    project = projects[int(input("Selecione o Projeto: "))]

    # 2. Seleção de Board (extraindo do 'included' do projeto)
    proj_resp = importer.session.get(f"{importer.url}/projects/{project['id']}").json()
    boards = proj_resp.get("included", {}).get("boards", [])
    for i, b in enumerate(boards):
        print(f"[{i}] {b['name']}")
    board = boards[int(input("Selecione o Board: "))]

    # 3. Mapeamento Inicial (Cache de Listas e Labels existentes no Board)
    print("\nMapeando estrutura existente do Board...")
    board_data = importer.get_board_details(board["id"])
    included = board_data.get("included", {})

    # Preenche Cache de Listas
    for l in included.get("lists", []):
        importer.list_cache[l["name"]] = l["id"]

    # Preenche Cache de Labels
    for lab in included.get("labels", []):
        key = f"{lab['name']}_{lab['color']}"
        importer.label_cache[key] = lab["id"]

    # 4. Processamento do JSON
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        tasks_data = json.load(f)
        if not isinstance(tasks_data, list):
            tasks_data = [tasks_data]

    print(f"\nIniciando importação de {len(tasks_data)} tarefas...\n")

    for idx, t in enumerate(tasks_data):
        cat_name = t.get("category", "Geral")

        # --- Lógica de Identificação/Criação de Listas ---
        if cat_name not in importer.list_cache:
            print(f"Criando nova lista: {cat_name}")
            new_list = importer.create_list(board["id"], cat_name, (idx + 1) * 65536)
            if new_list:
                importer.list_cache[cat_name] = new_list["id"]
            else:
                print(f"Erro ao criar lista '{cat_name}'. Pulando tarefa.")
                continue

        list_id = importer.list_cache[cat_name]

        # --- Criação do Card ---
        print(f" -> Importando Card: {t['taskName']} na lista [{cat_name}]")
        card = importer.create_card(list_id, t, (idx + 1) * 65536)
        if not card:
            continue

        # --- Processamento de Labels ---
        if "labels" in t:
            for lab_data in t["labels"]:
                l_name = lab_data["name"]
                l_color = lab_data.get("color", "morning-sky")
                cache_key = f"{l_name}_{l_color}"

                if cache_key not in importer.label_cache:
                    new_label = importer.create_label(board["id"], l_name, l_color)
                    if new_label:
                        importer.label_cache[cache_key] = new_label["id"]

                if cache_key in importer.label_cache:
                    importer.add_label_to_card(
                        card["id"], importer.label_cache[cache_key]
                    )

        # --- Processamento de Checklists ---
        if t.get("checkList"):
            importer.create_checklist_structure(card["id"], t["checkList"])

    print("\nImportação finalizada com sucesso!")


if __name__ == "__main__":
    main()
