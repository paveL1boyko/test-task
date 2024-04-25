# Инструкция по запуску стриминга логов

## Введение

Данная инструкция поможет вам настроить и запустить стриминг логов из Docker-контейнера в AWS CloudWatch.

## Предварительные требования

- Установленный Docker
- Установленный Poetry

## Установка

1. **Установка Poetry:**

    Для установки Poetry выполните следующую команду:

    ```bash
    curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -
    ```

2. **Настройка виртуального окружения:**

    Перейдите в директорию вашего проекта и активируйте виртуальное окружение:

    ```bash
    poetry shell
    ```

3. **Установка зависимостей:**

    Установите необходимые зависимости через Poetry:

    ```bash
    poetry install
    ```

## Запуск

Для запуска стриминга логов выполните следующую команду:

экспортируем переменные окружения
```bash
export AWS_ACCESS_KEY_ID='your_access_key'
export AWS_SECRET_ACCESS_KEY='your_secret_key'
```
запус стриминга
```bash
python main.py --docker-image python --bash-command "pip install -U pip && pip install tqdm && python -u -c \"exec('import time\\ncounter=0\\nwhile True:\\n print(counter)\\n counter+=1\\n time.sleep(0.1)')\"" --aws-cloudwatch-group test-task-group-1 --aws-cloudwatch-stream test-task-stream-1 --aws-access-key-id $AWS_ACCESS_KEY_ID --aws-secret-access-key $AWS_SECRET_ACCESS_KEY --aws-region us-west-2
```
