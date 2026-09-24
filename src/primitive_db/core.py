"""Управление таблицами, проверка схем и операции с записями."""

import json

from primitive_db.constants import ID_COLUMN, VALID_TYPES
from primitive_db.decorators import (
    confirm_action,
    create_cacher,
    handle_db_errors,
    log_time,
)
from primitive_db.utils import load_table_data, validate_name

select_cache = create_cacher()


def get_schema(metadata, table_name):
    """Возвращает типы столбцов существующей таблицы."""
    validate_name(table_name)
    if table_name not in metadata:
        raise KeyError(table_name)
    return dict(column.split(":") for column in metadata[table_name])


def validate_fields(schema, fields, allow_id=True):
    """Проверяет имена и точные типы значений, отличая bool от int."""
    for name, value in fields.items():
        if name not in schema:
            raise KeyError(name)
        if not allow_id and name == ID_COLUMN:
            raise ValueError("ID создаётся автоматически и не изменяется.")
        if type(value) is not VALID_TYPES[schema[name]]:
            raise ValueError(f'Столбец "{name}" ожидает тип {schema[name]}.')


@handle_db_errors
def create_table(metadata, table_name, columns):
    """Создаёт схему с ID первым столбцом и возвращает метаданные."""
    validate_name(table_name)
    if table_name in metadata:
        print(f'Ошибка: Таблица "{table_name}" уже существует.')
        return None
    schema = {ID_COLUMN: "int"}
    seen = set()
    if not columns:
        raise ValueError("Укажите хотя бы один столбец.")
    for column in columns:
        parts = column.split(":")
        if len(parts) != 2:
            raise ValueError(f"Некорректное значение: {column}. Попробуйте снова.")
        name, data_type = parts
        validate_name(name)
        if name in seen or data_type not in VALID_TYPES:
            raise ValueError(f"Некорректное значение: {column}. Попробуйте снова.")
        if name == ID_COLUMN and data_type != "int":
            raise ValueError("Столбец ID должен иметь тип int.")
        seen.add(name)
        schema[name] = data_type
    metadata[table_name] = [f"{name}:{kind}" for name, kind in schema.items()]
    select_cache.clear()
    return metadata


@handle_db_errors
@confirm_action("удаление таблицы")
def drop_table(metadata, table_name):
    """Удаляет схему таблицы после подтверждения."""
    if table_name not in metadata:
        print(f'Ошибка: Таблица "{table_name}" не существует.')
        return None
    del metadata[table_name]
    select_cache.clear()
    return metadata


@handle_db_errors
@log_time
def insert(metadata, table_name, values):
    """Проверяет значения и добавляет запись с автоматически созданным ID."""
    schema = get_schema(metadata, table_name)
    names = [name for name in schema if name != ID_COLUMN]
    if len(values) != len(names):
        raise ValueError(f"Ожидается значений: {len(names)}, получено: {len(values)}.")
    fields = dict(zip(names, values))
    validate_fields(schema, fields)
    data = load_table_data(table_name)
    next_id = max((row[ID_COLUMN] for row in data), default=0) + 1
    data.append({ID_COLUMN: next_id, **fields})
    select_cache.clear()
    return data


def matches(row, where_clause):
    """Проверяет равенство значений и их типов в условии."""
    return all(
        type(row[name]) is type(value) and row[name] == value
        for name, value in (where_clause or {}).items()
    )


@handle_db_errors
@log_time
def select(table_data, where_clause=None):
    """Возвращает копии подходящих записей, кешируя одинаковые запросы."""
    # Снимок данных в ключе учитывает также изменения файлов между командами.
    key = json.dumps([table_data, where_clause], sort_keys=True, ensure_ascii=False)
    rows = select_cache(
        key, lambda: [row.copy() for row in table_data if matches(row, where_clause)]
    )
    return [row.copy() for row in rows]


@handle_db_errors
def update(table_data, set_clause, where_clause):
    """Возвращает новые записи с обновлёнными полями выбранных строк."""
    if not where_clause or not set_clause:
        raise ValueError("Для update требуются set и where.")
    if ID_COLUMN in set_clause:
        raise ValueError("ID создаётся автоматически и не изменяется.")
    result = []
    for row in table_data:
        for name, value in set_clause.items():
            if type(row[name]) is not type(value):
                raise ValueError(f'Неверный тип значения столбца "{name}".')
        result.append(
            {**row, **set_clause} if matches(row, where_clause) else row.copy()
        )
    select_cache.clear()
    return result


@handle_db_errors
@confirm_action("удаление записей")
def delete(table_data, where_clause):
    """Возвращает записи, оставшиеся после подтверждённого удаления."""
    if not where_clause:
        raise ValueError("Для delete требуется where.")
    result = [row.copy() for row in table_data if not matches(row, where_clause)]
    select_cache.clear()
    return result
