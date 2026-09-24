"""Загрузка и сохранение метаданных и записей в JSON."""

import json
import os

from primitive_db.constants import DATA_DIR, ENCODING


def validate_name(name):
    """Проверяет, что имя таблицы или столбца является идентификатором."""
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError(f"Некорректное значение: {name}. Попробуйте снова.")


def load_json(filepath, default):
    """Читает JSON; для отсутствующего файла возвращает начальное значение."""
    try:
        with open(filepath, encoding=ENCODING) as source:
            return json.load(source)
    except FileNotFoundError:
        return default


def save_json(filepath, data):
    """Заменяет файл только после успешной записи нового JSON."""
    temporary_path = f"{filepath}.tmp"
    with open(temporary_path, "w", encoding=ENCODING) as target:
        json.dump(data, target, ensure_ascii=False, indent=2)
    os.replace(temporary_path, filepath)


def load_metadata(filepath):
    """Загружает словарь схем таблиц или пустой словарь при первом запуске."""
    metadata = load_json(filepath, {})
    if not isinstance(metadata, dict):
        raise ValueError("Метаданные должны быть словарём.")
    return metadata


def save_metadata(filepath, data):
    """Сохраняет схемы таблиц."""
    save_json(filepath, data)


def table_path(table_name):
    """Возвращает путь к файлу таблицы с проверенным именем."""
    validate_name(table_name)
    return os.path.join(DATA_DIR, f"{table_name}.json")


def load_table_data(table_name):
    """Загружает записи таблицы или пустой список для новой таблицы."""
    data = load_json(table_path(table_name), [])
    if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
        raise ValueError("Данные таблицы должны быть списком записей.")
    return data


def save_table_data(table_name, data):
    """Сохраняет записи, при необходимости создаёт каталог data."""
    filepath = table_path(table_name)
    os.makedirs(DATA_DIR, exist_ok=True)
    save_json(filepath, data)


def remove_table_data(table_name):
    """Удаляет файл данных вместе с таблицей."""
    filepath = table_path(table_name)
    if os.path.exists(filepath):
        os.remove(filepath)
