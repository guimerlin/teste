import json
import requests
import os
import time

# --- Configurações do Planka ---
PLANKA_URL = "http://bandito.site:3000/api"
USERNAME = "luizbraga@live.com"
PASSWORD = "gui123321"
JSON_FILE = "tasks.json"

# --- Funções da Documentação Planka ---


def get_token():
    url = f"{PLANKA_URL}/access-tokens"
    payload = {"emailOrUsername": USERNAME, "password": PASSWORD}
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        # Procura o token em diferentes chaves possíveis
        for key in ["token", "item", "id"]:
            if key in data:
                return data[key]
    except requests.RequestException as e:
        print(f"Erro ao obter token: {e}")
        return None
    return None


def get_projects(token):
    url = f"{PLANKA_URL}/projects"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    return response.json().get("items", []) if response.ok else []


def get_project_boards(project_id, token):
    url = f"{PLANKA_URL}/projects/{project_id}"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    if response.ok:
        data = response.json()
        # Tenta extrair boards do 'included' conforme seu log anterior
        included = data.get("included", {})
        if isinstance(included, dict):
            return included.get("boards", [])
    return []


def create_planka_list(board_id, name, token, position=65536):
    url = f"{PLANKA_URL}/boards/{board_id}/lists"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "type": "active",  # Conforme sua whitelist: active
        "name": name[:128],
        "position": position,
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()["item"] if response.ok else None


def create_planka_card(list_id, card_data, token, position=65536):
    url = f"{PLANKA_URL}/lists/{list_id}/cards"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "type": "project",  # Conforme sua whitelist: project
        "name": card_data.get("taskName", "Sem Nome")[:1024],
        "description": card_data.get("description"),
        "position": position,
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()["item"] if response.ok else None


def create_planka_task_list(card_id, name, token, position=65536):
    # ESSA É A CHAVE: Cria a "caixa" de checklist antes das tarefas
    url = f"{PLANKA_URL}/cards/{card_id}/task-lists"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "name": name[:128],
        "position": position,
        "showOnFrontOfCard": True,
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()["item"] if response.ok else None


def create_planka_task(
    task_list_id, task_name, token, is_completed=False, position=65536
):
    url = f"{PLANKA_URL}/task-lists/{task_list_id}/tasks"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "name": task_name[:1024],
        "position": position,
        "isCompleted": is_completed,
        "type": "task",
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()["item"] if response.ok else None


# --- Lógica Principal ---


def main():
    token = get_token()
    if not token:
        return

    # 1. Seleção de Projeto
    projects = get_projects(token)
    for i, p in enumerate(projects):
        print(f"[{i}] {p['name']}")
    p_idx = int(input("Escolha o Projeto: "))
    project = projects[p_idx]

    # 2. Seleção de Board
    boards = get_project_boards(project["id"], token)
    for i, b in enumerate(boards):
        print(f"[{i}] {b['name']}")
    b_idx = int(input("Escolha o Board: "))
    board = boards[b_idx]

    # 3. Mapear listas existentes no Board para evitar duplicados
    # (Poderíamos buscar as listas do board aqui se necessário)
    existing_lists = {}

    # 4. Ler JSON
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            tasks_data = json.load(f)
            if not isinstance(tasks_data, list):
                tasks_data = [tasks_data]
    except Exception as e:
        print(f"Erro ao ler JSON: {e}")
        return

    print(f"\nIniciando importação para o board: {board['name']}")

    for idx, task in enumerate(tasks_data):
        cat_name = task.get("category", "Geral")

        # Cria ou recupera a lista (simplificado)
        if cat_name not in existing_lists:
            print(f"Criando lista: {cat_name}")
            new_list = create_planka_list(
                board["id"], cat_name, token, (idx + 1) * 65536
            )
            if new_list:
                existing_lists[cat_name] = new_list["id"]
            else:
                continue

        list_id = existing_lists[cat_name]

        # Cria o Card
        print(f" -> Card: {task.get('taskName')}")
        card = create_planka_card(list_id, task, token, (idx + 1) * 65536)

        # Se tiver checklist, segue a hierarquia da documentação: Card -> Task List -> Task
        if card and task.get("checkList"):
            # Cria a Task List (Checklist) dentro do card
            t_list = create_planka_task_list(card["id"], "Checklist", token)

            if t_list:
                for i, item in enumerate(task["checkList"]):
                    item_name = (
                        item if isinstance(item, str) else item.get("text", "Tarefa")
                    )
                    is_done = (
                        False if isinstance(item, str) else item.get("done", False)
                    )

                    # Cria a tarefa dentro da Task List
                    create_planka_task(
                        t_list["id"], item_name, token, is_done, (i + 1) * 65536
                    )

        time.sleep(0.05)

    print("\nImportação concluída!")


if __name__ == "__main__":
    main()
