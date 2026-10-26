import math
from datetime import *
from flask import Flask, request, jsonify

app = Flask(__name__)

now = datetime.now(timezone.utc)
tasks = [
    {
        "id": 1,
        "title": "Купить молоко",
        "done": True,
        "created_at": (now + timedelta(seconds=1)).isoformat()
    },
    {
        "id": 2,
        "title": "Выучить REST",
        "done": False,
        "created_at": (now + timedelta(seconds=2)).isoformat()
    },
    {
        "id": 3,
        "title": "Сдать лабораторную",
        "done": True,
        "created_at": (now + timedelta(seconds=3)).isoformat()
    },
    {
        "id": 4,
        "title": "Проверить почту",
        "done": False,
        "created_at": (now + timedelta(seconds=4)).isoformat()
    },
    {
        "id": 5,
        "title": "Позвонить маме",
        "done": False,
        "created_at": (now + timedelta(seconds=5)).isoformat()
    },
]

next_id = 6


def clean_spaces(text: str) -> str:
    return " ".join(text.strip().split())


def validate_title(title, current_task_id=None):
    if not isinstance(title, str):
        return None, ("Поле title должно быть строкой", 400)
    
    cleaned = clean_spaces(title)
    if not cleaned:
        return None, ("Название задачи не может быть пустым", 422)
    if len(cleaned) > 200:
        return None, ("Длина заголовка не должна превышать 200 символов", 400)

    # Проверка на дубликаты
    for t in tasks:
        if current_task_id is not None and t["id"] == current_task_id:
            continue
        if clean_spaces(t["title"]).lower() == cleaned.lower():
            return None, ("Задача с таким названием уже существует", 409)

    return cleaned, None


@app.get("/")
def service_info():
    return jsonify({
        "service": "ToDo API",
        "endpoints": [
            "GET /",
            "GET /tasks",
            "GET /tasks/<id>",
            "POST /tasks",
            "PUT /tasks/<id>",
            "PATCH /tasks/<id>",
            "DELETE /tasks/<id>"
        ]
    }), 200


@app.get("/tasks")
def list_tasks():
    res = list(tasks)

    done_param = request.args.get("done")
    if done_param is not None:
        if done_param.lower() == "true":
            res = [t for t in res if t["done"] is True]
        elif done_param.lower() == "false":
            res = [t for t in res if t["done"] is False]
        else:
            return jsonify({"error": "Невалидное значение done"}), 400

    q_param = request.args.get("q")
    if q_param is not None:
        res = [t for t in res if q_param.lower() in t["title"].lower()]

    sort_field = request.args.get("sort", "id")
    order = request.args.get("order", "asc").lower()

    if sort_field not in ["id", "title", "created_at"]:
        return jsonify({"error": "Невалидное поле сортировки"}), 400
    if order not in ["asc", "desc"]:
        return jsonify({"error": "Невалидный порядок сортировки"}), 400

    reverse = (order == "desc")
    if sort_field == "title":
        res.sort(key=lambda x: x["title"].lower(), reverse=reverse)
    else:
        res.sort(key=lambda x: x[sort_field], reverse=reverse)

    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 10))
    except ValueError:
        return jsonify({"error": "page и per_page должны быть числами"}), 400

    if page < 1 or per_page < 1 or per_page > 100:
        return jsonify({"error": "Параметры пагинации вне диапазона"}), 400

    total = len(res)
    pages = math.ceil(total / per_page) if total > 0 else 0

    start = (page - 1) * per_page
    end = start + per_page
    items = res[start:end] if start < total else []

    return jsonify({
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages
    }), 200


@app.get("/tasks/<int:task_id>")
def get_task(task_id):
    for t in tasks:
        if t["id"] == task_id:
            return jsonify(t), 200
    return jsonify({"error": "Задача не найдена"}), 404


@app.post("/tasks")
def create_task():
    global next_id
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or "title" not in data:
        return jsonify({"error": "Поле title обязательно"}), 400

    title, err = validate_title(data["title"])
    if err:
        return jsonify({"error": err[0]}), err[1]

    done = data.get("done", False)
    if not isinstance(done, bool):
        return jsonify({"error": "done должно быть bool"}), 400

    task = {
        "id": next_id,
        "title": title,
        "done": done,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    tasks.append(task)
    next_id += 1
    return jsonify(task), 201


@app.put("/tasks/<int:task_id>")
def replace_task(task_id):
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        return jsonify({"error": "Задача не найдена"}), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or "title" not in data:
        return jsonify({"error": "Поле title обязательно"}), 400

    title, err = validate_title(data["title"], current_task_id=task_id)
    if err:
        return jsonify({"error": err[0]}), err[1]

    done = data.get("done", False)
    if not isinstance(done, bool):
        return jsonify({"error": "done должно быть bool"}), 400

    task["title"] = title
    task["done"] = done
    return jsonify(task), 200


@app.patch("/tasks/<int:task_id>")
def update_task(task_id):
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        return jsonify({"error": "Задача не найдена"}), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Ожидался JSON-объект"}), 400

    if "title" in data:
        title, err = validate_title(data["title"], current_task_id=task_id)
        if err:
            return jsonify({"error": err[0]}), err[1]
        task["title"] = title

    if "done" in data:
        if not isinstance(data["done"], bool):
            return jsonify({"error": "done должно быть bool"}), 400
        task["done"] = data["done"]

    return jsonify(task), 200


@app.delete("/tasks/<int:task_id>")
def delete_task(task_id):
    global tasks
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        return jsonify({"error": "Задача не найдена"}), 404

    tasks = [t for t in tasks if t["id"] != task_id]
    return "", 204


if __name__ == "__main__":
    app.run(debug=True, port=5000)