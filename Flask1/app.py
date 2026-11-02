import math
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify

app = Flask(__name__)
app.json.ensure_ascii = False

tasks = []
next_id = 1

MAX_TITLE_LEN = 200
DEFAULT_PER_PAGE = 10
MAX_PER_PAGE = 100


def now_iso():
    """Текущее время в ISO 8601 UTC."""
    return datetime.now(timezone.utc).isoformat()


def normalize(title):
    """Нормализация title для сравнения: убрать пробелы и перевести в нижний регистр."""
    return " ".join(title.split()).lower()


def err(message, code):
    """JSON-ответ об ошибке: {"error": message} с заданным кодом."""
    return jsonify({"error": message}), code


def find_task(task_id):
    """Найти задачу по id или вернуть None."""
    for task in tasks:
        if task["id"] == task_id:
            return task
    return None


def title_exists(title, exclude_id=None):
    """Есть ли уже задача с таким title (с нормализацией)?

    exclude_id — id задачи, которую переименовываем (её собственное название
    дубликатом не считается).
    """
    norm = normalize(title)
    return any(
        normalize(t["title"]) == norm
        for t in tasks
        if exclude_id is None or t["id"] != exclude_id
    )


def validate_title(data, exclude_id=None):
    """Валидация title. Возвращает (title, None) или (None, error_response).

    Правила:
      - отсутствует           -> 400
      - не строка / пустая    -> 422
      - длиннее MAX_TITLE_LEN -> 422
      - дубликат              -> 409
    """
    if not isinstance(data, dict) or "title" not in data:
        return None, err("Поле title обязательно", 400)

    title = data["title"]
    if not isinstance(title, str) or not title.strip():
        return None, err("Поле title должно быть непустой строкой", 422)

    stripped = title.strip()
    if len(stripped) > MAX_TITLE_LEN:
        return None, err(f"Длина поля title не должна превышать {MAX_TITLE_LEN} символов", 422)

    if title_exists(stripped, exclude_id=exclude_id):
        return None, err("Задача с таким названием уже существует", 409)

    return stripped, None


def parse_done(value, default=False):
    """Приведение поля done к boolean."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1")
    return bool(value)


def seed():
    """Заполнить хранилище демонстрационными задачами при старте."""
    global tasks, next_id
    now = datetime.now(timezone.utc)
    demo_tasks = [
        ("Купить молоко", True),
        ("Выучить REST", False),
        ("Сдать лабораторную", True),
        ("Проверить почту", False),
        ("Позвонить маме", False),
    ]
    tasks.clear()
    for i, (title, done) in enumerate(demo_tasks):
        tasks.append({
            "id": i + 1,
            "title": title,
            "done": done,
            "created_at": (now - timedelta(hours=5 - i)).isoformat(),
        })
    next_id = 6


def get_json_data():
    try:
        if request.is_json:
            raw = request.get_json(silent=True)
        elif request.data:
            raw = request.get_json(force=True, silent=True)
        else:
            return None, False
    except Exception:
        return None, False

    if not isinstance(raw, dict):
        return None, False

    return raw, True


# Вызов seed() при импорте модуля
seed()


# ---------------------------------------------------------------------------
# Вьюхи
# ---------------------------------------------------------------------------


@app.get("/tasks")
def list_tasks():
    """GET /tasks — список с фильтрами, сортировкой и пагинацией.

    Query: done, q, sort, order, page, per_page.
    Ответ: {items, page, per_page, total, pages}.
    """
    filtered = list(tasks)

    # Фильтр done
    done_param = request.args.get("done")
    if done_param is not None:
        if done_param.lower() == "true":
            filtered = [t for t in filtered if t["done"] is True]
        elif done_param.lower() == "false":
            filtered = [t for t in filtered if t["done"] is False]
        else:
            return err("Параметр done должен иметь значение true или false", 400)

    # Поиск q
    q_param = request.args.get("q")
    if q_param is not None:
        q_norm = normalize(q_param)
        filtered = [t for t in filtered if q_norm in normalize(t["title"])]

    # Сортировка sort 
    sort = request.args.get("sort", "created_at")
    if sort not in ("id", "title", "created_at"):
        return err("Параметр sort должен быть одним из: id, title, created_at", 400)

    # Порядок order
    order = request.args.get("order", "asc")
    if order not in ("asc", "desc"):
        return err("Параметр order должен быть 'asc' или 'desc'", 400)

    # Пагинация: page (целое >= 1, по умолчанию 1)
    page_param = request.args.get("page", 1)
    try:
        if isinstance(page_param, str) and "." in page_param:
            return err("Параметр page должен быть целым числом не меньше 1", 400)
        page = int(page_param)
        if page < 1:
            return err("Параметр page должен быть целым числом не меньше 1", 400)
    except (ValueError, TypeError):
        return err("Параметр page должен быть целым числом не меньше 1", 400)

    # Пагинация: per_page (целое от 1 до 100, по умолчанию 10)
    per_page_param = request.args.get("per_page", DEFAULT_PER_PAGE)
    try:
        if isinstance(per_page_param, str) and "." in per_page_param:
            return err(f"Параметр per_page должен быть целым числом от 1 до {MAX_PER_PAGE}", 400)
        per_page = int(per_page_param)
        if per_page < 1 or per_page > MAX_PER_PAGE:
            return err(f"Параметр per_page должен быть в диапазоне от 1 до {MAX_PER_PAGE}", 400)
    except (ValueError, TypeError):
        return err(f"Параметр per_page должен быть целым числом от 1 до {MAX_PER_PAGE}", 400)

    # Сортировка
    reverse = (order == "desc")
    filtered.sort(key=lambda t: t[sort], reverse=reverse)

    total = len(filtered)
    pages = max(1, math.ceil(total / per_page))

    start = (page - 1) * per_page
    end = start + per_page
    items = filtered[start:end]

    return jsonify({
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
    }), 200


@app.get("/tasks/<int:task_id>")
def get_task(task_id):
    """GET /tasks/<id> — одна задача. 404, если нет."""
    task = find_task(task_id)
    if task is None:
        return err("задача не найдена", 404)
    return jsonify(task), 200


@app.post("/tasks")
def create_task():
    """POST /tasks — создать задачу.

    Тело — JSON-объект {title, done?}.
    Валидация title через validate_title().
    Ответ 201 с созданной задачей.
    """
    global next_id
    data, is_valid = get_json_data()
    if not is_valid:
        return err("Тело запроса должно быть JSON-объектом", 400)

    title, error_response = validate_title(data)
    if error_response is not None:
        return error_response

    done = parse_done(data.get("done", False))

    new_task = {
        "id": next_id,
        "title": title,
        "done": done,
        "created_at": now_iso(),
    }
    next_id += 1
    tasks.append(new_task)
    return jsonify(new_task), 201


@app.put("/tasks/<int:task_id>")
def replace_task(task_id):
    """PUT /tasks/<id> — полная замена ресурса.

    Как POST, но: 404 если нет задачи; validate_title(..., exclude_id=task_id);
    отсутствующий done -> False.
    """
    task = find_task(task_id)
    if task is None:
        return err("задача не найдена", 404)

    data, is_valid = get_json_data()
    if not is_valid:
        return err("Тело запроса должно быть JSON-объектом", 400)

    title, error_response = validate_title(data, exclude_id=task_id)
    if error_response is not None:
        return error_response

    done = parse_done(data.get("done", False))

    task["title"] = title
    task["done"] = done
    return jsonify(task), 200


@app.patch("/tasks/<int:task_id>")
def update_task(task_id):
    """PATCH /tasks/<id> — частичное обновление.

    Обновляются только переданные поля (title и/или done).
    """
    task = find_task(task_id)
    if task is None:
        return err("задача не найдена", 404)

    data, is_valid = get_json_data()
    if not is_valid:
        return err("Тело запроса должно быть JSON-объектом", 400)

    if "title" in data:
        raw_title = data["title"]
        if not isinstance(raw_title, str) or not raw_title.strip():
            return err("Поле title должно быть непустой строкой", 422)
        stripped = raw_title.strip()
        if len(stripped) > MAX_TITLE_LEN:
            return err(f"Длина поля title не должна превышать {MAX_TITLE_LEN} символов", 422)
        if normalize(stripped) != normalize(task["title"]):
            if title_exists(stripped, exclude_id=task_id):
                return err("Задача с таким названием уже существует", 409)
        task["title"] = stripped

    if "done" in data:
        task["done"] = parse_done(data["done"])

    return jsonify(task), 200


@app.delete("/tasks/<int:task_id>")
def delete_task(task_id):
    """DELETE /tasks/<id> — удалить задачу. 204 или 404."""
    task = find_task(task_id)
    if task is None:
        return err("задача не найдена", 404)
    tasks.remove(task)
    return "", 204


@app.get("/")
def index():
    """GET / — описание сервиса."""
    return jsonify({
        "service": "tasks-api",
        "seed": len(tasks),
        "endpoints": [
            "GET / - описание сервиса",
            "GET /tasks - список задач с фильтрацией, сортировкой и пагинацией",
            "GET /tasks/<id> - получение одной задачи по id",
            "POST /tasks - создание новой задачи",
            "PUT /tasks/<id> - полная замена задачи",
            "PATCH /tasks/<id> - частичное обновление задачи",
            "DELETE /tasks/<id> - удаление задачи",
        ],
    }), 200


# Формат ошибок (5.1)
@app.errorhandler(400)
def handle_400(e):
    msg = e.description if hasattr(e, "description") and isinstance(e.description, str) and e.description != "Bad Request" else "Некорректный запрос"
    return err(msg, 400)


@app.errorhandler(404)
def handle_404(e):
    return err("Ресурс не найден", 404)


@app.errorhandler(405)
def handle_405(e):
    return err("Метод не поддерживается", 405)


@app.errorhandler(500)
def handle_500(e):
    return err("Внутренняя ошибка сервера", 500)


if __name__ == "__main__":
    app.run(debug=True)
