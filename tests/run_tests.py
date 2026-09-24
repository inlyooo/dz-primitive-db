"""Проверки команд, сохранения данных и декораторов в отдельных каталогах."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from primitive_db import core
from primitive_db.decorators import (
    confirm_action,
    create_cacher,
    handle_db_errors,
    log_time,
)
from primitive_db.engine import execute_command
from primitive_db.parser import parse_command, parse_set, parse_values, parse_where
from primitive_db.utils import load_metadata, load_table_data, save_table_data


def command(text, answer="y"):
    """Исполняет команду и возвращает её консольный вывод."""
    output = io.StringIO()
    with (
        contextlib.redirect_stdout(output),
        patch("prompt.string", return_value=answer),
    ):
        execute_command(text)
    return output.getvalue()


def create_users():
    """Создаёт таблицу для проверок CRUD."""
    command("create_table users name:str age:int is_active:bool")


def add_user(name="Sergei", age=28):
    """Добавляет типичную запись через консольную команду."""
    return command(f'insert into users values ("{name}", {age}, true)')


def test_full_crud_cycle():
    create_users()
    assert "ID=1" in add_user()
    assert "Sergei" in command("select from users where age = 28")
    assert "успешно обновлена" in command(
        'update users set age = 29 where name = "Sergei"'
    )
    assert load_table_data("users")[0]["age"] == 29
    assert "успешно удалена" in command("delete from users where ID = 1")
    assert "Количество записей: 0" in command("info users")
    assert "успешно удалена" in command("drop_table users")
    assert load_metadata("db_meta.json") == {}
    assert not os.path.exists("data/users.json")


def test_schema_validation_and_duplicate_table():
    create_users()
    original = load_metadata("db_meta.json")
    assert original["users"] == ["ID:int", "name:str", "age:int", "is_active:bool"]
    assert "уже существует" in command("create_table users title:str")
    for definition in ("age:float", "age:int age:str", "ID:str", "age", "a/b:str"):
        assert "Ошибка" in command(f"create_table invalid {definition}")
    assert load_metadata("db_meta.json") == original


def test_explicit_id_is_not_duplicated():
    command("create_table users name:str ID:int")
    assert load_metadata("db_meta.json")["users"] == ["ID:int", "name:str"]
    command('insert into users values ("Anna")')
    assert load_table_data("users") == [{"ID": 1, "name": "Anna"}]


def test_insert_rejects_wrong_counts_and_types():
    create_users()
    for values in (
        '("Anna", 28)',
        "(1, 28, true)",
        '("Anna", true, true)',
        '("Anna", 28, 1)',
        '("Anna", "28", true)',
        '(1, "Anna", 28, true)',
    ):
        assert "Ошибка" in command(f"insert into users values {values}")
    assert load_table_data("users") == []


def test_quoted_strings_and_escapes():
    command("create_table notes text:str")
    value = 'Привет, where = (set): "мир"'
    literal = json.dumps(value, ensure_ascii=False)
    assert "ID=1" in command(f"insert into notes values ({literal})")
    assert load_table_data("notes")[0]["text"] == value
    assert value in command(f"select from notes where text = {literal}")
    assert parse_values("('', 'a, b', -8, false)") == ["", "a, b", -8, False]


def test_parser_rejects_incomplete_commands():
    invalid = [
        "insert into users values ()",
        "insert into users values (1,)",
        "insert into users values (1 2)",
        'select from users where name = "Anna',
        "select from users where age == 1",
        "delete from users",
        "update users set age = 1",
        "select from users trailing",
        "help extra",
        "insert into users values (unquoted)",
    ]
    for text in invalid:
        assert "Ошибка" in command(text), text


def test_conditions_and_multiple_assignments():
    assert parse_where('name = "28"') == {"name": "28"}
    assert parse_set('age=29, name="Anna, Maria"') == {"age": 29, "name": "Anna, Maria"}
    assert parse_command('update users set where="set" where where="where"') == (
        "update",
        ("users", {"where": "set"}, {"where": "where"}),
    )
    create_users()
    add_user()
    command('update users set age=29, name="Anna, Maria" where ID=1')
    assert load_table_data("users")[0] == {
        "ID": 1,
        "name": "Anna, Maria",
        "age": 29,
        "is_active": True,
    }


def test_multiple_matching_rows():
    create_users()
    add_user("Anna")
    add_user("Boris")
    add_user("Vera", 40)
    output = command("update users set is_active = false where age = 28")
    assert "ID=1" in output and "ID=2" in output and "ID=3" not in output
    command("delete from users where is_active = false")
    assert [row["ID"] for row in load_table_data("users")] == [3]


def test_ids_remain_unique_after_deletion():
    create_users()
    for name in ("Anna", "Boris", "Vera"):
        add_user(name)
    command("delete from users where ID=2")
    assert "ID=4" in add_user("Dima")
    assert [row["ID"] for row in load_table_data("users")] == [1, 3, 4]


def test_cancel_preserves_files():
    create_users()
    add_user()
    with open("data/users.json", "rb") as source:
        original = source.read()
    assert "Операция отменена" in command("delete from users where ID=1", answer="n")
    assert "Операция отменена" in command("drop_table users", answer="")
    with open("data/users.json", "rb") as source:
        assert source.read() == original
    assert "users" in load_metadata("db_meta.json")


def test_unknown_fields_and_types_on_empty_table():
    create_users()
    for text in (
        "select from users where unknown=1",
        "delete from users where unknown=1",
        "update users set unknown=1 where ID=1",
        "select from users where age=true",
        'update users set age="29" where ID=1',
    ):
        assert "Ошибка" in command(text), text
    assert load_table_data("users") == []


def test_failed_update_is_atomic():
    create_users()
    add_user()
    original = load_table_data("users")
    for assignment in ('name="Changed", age=true', "ID=42", "age=29, age=30"):
        assert "Ошибка" in command(f"update users set {assignment} where ID=1")
        assert load_table_data("users") == original


def test_missing_tables_and_unknown_command():
    assert "не существует" in command("drop_table missing")
    assert "Ошибка" in command("select from missing")
    assert "Функции nonsense нет. Попробуйте снова." in command("nonsense")
    assert "Таблиц пока нет" in command("list_tables")
    assert "create_table" in command("help")


def test_names_cannot_escape_data_directory():
    for name in ("../users", "a/b", "a\\b", "..", "users.json"):
        assert "Ошибка" in command(f"create_table {name} name:str")
    assert not os.path.exists("db_meta.json")


def test_select_stays_current_after_every_mutation():
    create_users()
    assert "Anna" not in command("select from users")
    add_user("Anna")
    assert "Anna" in command("select from users")
    command('update users set name="Boris" where ID=1')
    assert "Boris" in command("select from users")
    assert "Anna" not in command("select from users")
    command("delete from users where ID=1")
    assert "Boris" not in command("select from users")
    command("drop_table users")
    create_users()
    assert "Boris" not in command("select from users")


def test_cache_handles_external_edits_and_returned_mutation():
    create_users()
    add_user("Anna")
    command("select from users")
    data = load_table_data("users")
    data[0]["name"] = "Boris"
    save_table_data("users", data)
    assert "Boris" in command("select from users")
    with contextlib.redirect_stdout(io.StringIO()):
        rows = core.select(data)
        rows[0]["name"] = "Changed"
        assert core.select(data)[0]["name"] == "Boris"


def test_corrupt_json_is_reported_and_preserved():
    create_users()
    with open("data/users.json", "w", encoding="utf-8") as target:
        target.write("{broken")
    assert "Ошибка валидации" in command("select from users")
    assert "Ошибка валидации" in add_user()
    with open("data/users.json", encoding="utf-8") as source:
        assert source.read() == "{broken"


def test_decorators_cache_and_timing():
    cacher = create_cacher()
    calls = []

    def calculate():
        calls.append(1)
        return 42

    assert cacher("key", calculate) == cacher("key", calculate) == 42
    assert len(calls) == 1
    cacher.clear()
    assert cacher("key", calculate) == 42 and len(calls) == 2
    output = io.StringIO()
    with (
        contextlib.redirect_stdout(output),
        patch("time.monotonic", side_effect=[1, 1.125]),
    ):
        assert log_time(calculate)() == 42
    assert "calculate выполнилась за 0.125 секунд" in output.getvalue()
    wrapped = confirm_action("проверка")(calculate)
    with contextlib.redirect_stdout(output), patch("prompt.string", return_value="n"):
        before = len(calls)
        assert wrapped() is None and len(calls) == before
    assert wrapped.__name__ == "calculate"


def test_error_decorator():
    for error in (KeyError("column"), ValueError("type"), FileNotFoundError()):

        def fail(error=error):
            raise error

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            assert handle_db_errors(fail)() is None
        assert "Ошибка" in output.getvalue()


def run_cli(text):
    """Запускает новый процесс приложения с UTF-8 для проверки персистентности."""
    return subprocess.run(
        [sys.executable, "-m", "primitive_db.main"],
        input=text,
        capture_output=True,
        encoding="utf-8",
        timeout=15,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=True,
    ).stdout


def test_cli_restart_persistence_and_eof():
    first = run_cli(
        "create_table users name:str age:int is_active:bool\n"
        'insert into users values ("Анна", 28, true)\nexit\n'
    )
    assert "ID=1" in first
    second = run_cli("list_tables\nselect from users\ninfo users\n")
    assert (
        "- users" in second and "Анна" in second and "Количество записей: 1" in second
    )
    assert "До свидания" in second


def isolated(test):
    """Запускает проверку в новом каталоге, не затрагивая пользовательскую базу."""

    def run():
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                core.select_cache.clear()
                test()
            finally:
                os.chdir(previous)

    run.__name__ = test.__name__
    return run


if __name__ == "__main__":
    suite = unittest.TestSuite(
        unittest.FunctionTestCase(isolated(test), description=name)
        for name, test in sorted(globals().copy().items())
        if name.startswith("test_")
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
