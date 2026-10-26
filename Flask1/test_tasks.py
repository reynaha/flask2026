import requests

BASE_URL = 'http://localhost:5000'

def test_todo_api():
    #Проверка GET
    r = requests.get(f'{BASE_URL}/')
    print('1. GET / ->', r.status_code, r.json())

    r = requests.get(f'{BASE_URL}/tasks?page=1&per_page=3')
    print('2. GET /tasks?page=1&per_page=3 ->', r.status_code, r.json())

    #Фильтр по статусу
    r = requests.get(f'{BASE_URL}/tasks?done=true')
    print('3. GET /tasks?done=true (total) ->', r.json().get('total'))

    #Поиск по подстроке
    r = requests.get(f'{BASE_URL}/tasks?q=REST')
    print('4. GET /tasks?q=REST ->', [t['title'] for t in r.json().get('items', [])])

    #POST
    new_task = {"title": "Подготовить отчет по лабе"}
    r = requests.post(f'{BASE_URL}/tasks', json=new_task)
    created = r.json()
    print('5. POST /tasks ->', r.status_code, created)

    #Проверка запрета дубликатов
    r_dup = requests.post(f'{BASE_URL}/tasks', json={"title": "  подготовить   отчет по ЛАБЕ  "})
    print('6. POST duplicate ->', r_dup.status_code, r_dup.json().get('error'))

    #PATCH
    task_id = created['id']
    r = requests.patch(f'{BASE_URL}/tasks/{task_id}', json={"done": True})
    print('7. PATCH /tasks/<id> ->', r.status_code, r.json())

    #DELETE
    r = requests.delete(f'{BASE_URL}/tasks/{task_id}')
    print('8. DELETE /tasks/<id> ->', r.status_code)

    #Повторное удаление(404)
    r_del_again = requests.delete(f'{BASE_URL}/tasks/{task_id}')
    print('9. DELETE again ->', r_del_again.status_code)

if __name__ == '__main__':
    test_todo_api()