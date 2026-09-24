"""Консольный цикл, вызов команд, сохранение и вывод результатов."""

import prompt
from prettytable import PrettyTable

from primitive_db import core
from primitive_db.constants import COMMAND_PROMPT, HELP, ID_COLUMN, META_FILE
from primitive_db.decorators import handle_db_errors
from primitive_db.parser import parse_command
from primitive_db.utils import (
    load_metadata,
    load_table_data,
    remove_table_data,
    save_metadata,
    save_table_data,
)


def print_help():
    """Показывает доступные команды и правила ввода значений."""
    print(HELP)


def show_rows(schema, rows):
    """Выводит записи в виде таблицы, включая заголовок пустого результата."""
    table = PrettyTable(list(schema))
    for row in rows:
        table.add_row([row[name] for name in schema])
    print(table)


def manage_table(command, metadata, arguments):
    """Создаёт или удаляет таблицу и сохраняет метаданные."""
    table_name = arguments[0]
    if command == "create_table":
        result = core.create_table(metadata, *arguments)
        if result is not None:
            save_table_data(table_name, [])
            save_metadata(META_FILE, result)
            columns = ", ".join(result[table_name])
            print(f'Таблица "{table_name}" успешно создана со столбцами: {columns}')
    else:
        if table_name not in metadata:
            print(f'Ошибка: Таблица "{table_name}" не существует.')
            return
        result = core.drop_table(metadata, table_name)
        if result is not None:
            remove_table_data(table_name)
            save_metadata(META_FILE, result)
            print(f'Таблица "{table_name}" успешно удалена.')


def execute_data_command(command, metadata, arguments):
    """Проверяет схему и выполняет команду над записями."""
    table_name = arguments[0]
    schema = core.get_schema(metadata, table_name)
    if command == "insert":
        result = core.insert(metadata, *arguments)
        if result is not None:
            save_table_data(table_name, result)
            record_id = result[-1][ID_COLUMN]
            print(
                f'Запись с ID={record_id} успешно добавлена в таблицу "{table_name}".'
            )
        return
    data = load_table_data(table_name)
    if command == "info":
        print(f"Таблица: {table_name}")
        print(f"Столбцы: {', '.join(metadata[table_name])}")
        print(f"Количество записей: {len(data)}")
        return
    where_clause = arguments[-1]
    core.validate_fields(schema, where_clause or {})
    if command == "select":
        result = core.select(data, where_clause)
        if result is not None:
            show_rows(schema, result)
        return
    if command == "update":
        core.validate_fields(schema, arguments[1], allow_id=False)
        result = core.update(data, arguments[1], where_clause)
    else:
        result = core.delete(data, where_clause)
    if result is None:
        return
    save_table_data(table_name, result)
    affected = [row[ID_COLUMN] for row in data if core.matches(row, where_clause)]
    for record_id in affected:
        if command == "update":
            print(
                f'Запись с ID={record_id} в таблице "{table_name}" успешно обновлена.'
            )
        else:
            print(f'Запись с ID={record_id} успешно удалена из таблицы "{table_name}".')
    if not affected:
        print("Подходящих записей нет.")


@handle_db_errors
def execute_command(text):
    """Обрабатывает одну команду; False означает выход из программы."""
    command, arguments = parse_command(text)
    if command == "exit":
        return False
    if not command:
        return True
    if command == "help":
        print_help()
        return True
    if command == "unknown":
        print(f"Функции {arguments[0]} нет. Попробуйте снова.")
        return True
    metadata = load_metadata(META_FILE)
    if command == "list_tables":
        for name in metadata:
            print(f"- {name}")
        if not metadata:
            print("Таблиц пока нет.")
    elif command in ("create_table", "drop_table"):
        manage_table(command, metadata, arguments)
    else:
        execute_data_command(command, metadata, arguments)
    return True


def run():
    """Запрашивает команды до exit, конца ввода или Ctrl+C."""
    print_help()
    while True:
        try:
            text = prompt.string(COMMAND_PROMPT)
            if execute_command(text) is False:
                break
        except (EOFError, KeyboardInterrupt):
            print("\nДо свидания!")
            break
