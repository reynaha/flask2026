import os
import uuid
import json
import hashlib
from datetime import *
from flask import *

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(256)

# Настройка путей
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
DATA_FOLDER = os.path.join(BASE_DIR, 'data')
DATA_FILE = os.path.join(DATA_FOLDER, 'filebase.json')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB лимит

PROHIBITED_EXTENSIONS = {
    '.exe', '.sh', '.php', '.phtml', '.php3', '.php4', '.php5', '.phps',
    '.js', '.mjs', '.bat', '.cmd', '.vbs', '.vbe', '.wsf', '.wsh',
    '.py', '.pyc', '.pyw', '.com', '.scr', '.msi', '.msp', '.reg',
    '.ps1', '.psm1', '.psd1', '.bin', '.cgi', '.pl'
}


def load_filebase():
    # Загрузка json датабазы аплоуднутых файлов
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(dict(), f, ensure_ascii=False, indent=4)
        return dict()
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, dict) else dict()
    except (json.JSONDecodeError, OSError):
        return dict()


def save_filebase(filebase):
    # Сохранение json датабазы аплоуднутых файлов
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER, exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(filebase, f, ensure_ascii=False, indent=4)


def calculate_md5_hash(file_stream):
    hash_md5 = hashlib.md5()
    for chunk in iter(lambda: file_stream.read(4096), b""):
        hash_md5.update(chunk)
    file_stream.seek(0)
    return hash_md5.hexdigest()


@app.route('/', methods=['GET', 'POST'])
def index():
    filebase = load_filebase()

    if request.method == 'POST':
        if 'file' not in request.files:
            flash("Поле загрузки файла не найдено в запросе.", "error")
            return redirect(url_for('index'))

        file = request.files['file']

        user_filename = file.filename.strip() if file.filename else ""
        if not user_filename:
            flash("Файл не выбран. Выберите файл для загрузки.", "error")
            return redirect(url_for('index'))

        #Проверка расширения файла
        _, ext = os.path.splitext(user_filename)
        ext_lower = ext.lower()

        if not ext_lower:
            flash("Загрузка файлов без расширения запрещена.", "error")
            return redirect(url_for('index'))

        if ext_lower in PROHIBITED_EXTENSIONS:
            flash(f"Загрузка файлов с расширением '{ext_lower}' запрещена", "error")
            return redirect(url_for('index'))

        # Проверка md5 дупликатов
        file_md5 = calculate_md5_hash(file.stream)
        if file_md5 in filebase:
            duplicate = filebase[file_md5]
            flash(
                f"Ошибка: файл с таким же содержимым (MD5: {file_md5}) уже был загружен ранее под именем '{duplicate.get('user_filename')}'.",
                "error"
            )
            return redirect(url_for('index'))

        # Генерация UUID и определениие структуры вложенных папок
        folder_name = str(uuid.uuid4()).lower()
        sub1 = folder_name[:2]
        sub2 = folder_name[2:4]
        uuidfilename = f"{folder_name}{ext_lower}"

        target_dir = os.path.join(UPLOAD_FOLDER, sub1, sub2)
        os.makedirs(target_dir, exist_ok=True)

        full_disk_path = os.path.join(target_dir, uuidfilename)
        file.save(full_disk_path)

        file_path = f"uploads/{sub1}/{sub2}/{uuidfilename}"
        upload_date = datetime.now().isoformat()

        # Запись метадаты в словарь по md5 ключу
        filebase[file_md5] = {
            "user_filename": user_filename,
            "uuidfilename": uuidfilename,
            "file_path": file_path,
            "date": upload_date,
            "extension": ext_lower,
            "md5_hash": file_md5
        }

        save_filebase(filebase)
        flash(f"Файл '{user_filename}' успешно загружен.", "success")
        return redirect(url_for('index'))

    # GET запрос - загрузка и отображение файлов
    files_list = list(filebase.values())
    return render_template('upload.html', files=files_list)


@app.route('/uploads/<path:filepath>')
@app.route('/upload/<path:filepath>')
def uploaded_file(filepath):
    # Отправить загруженный файл с диска
    return send_from_directory(app.config['UPLOAD_FOLDER'], filepath)


if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(DATA_FOLDER, exist_ok=True)
    app.run(debug=True, host='127.0.0.1', port=5000)
