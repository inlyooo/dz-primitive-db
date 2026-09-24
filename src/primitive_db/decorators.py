"""Обработка ошибок, подтверждение действий и кеширование."""

import time

import prompt


def handle_db_errors(func):
    """Выводит понятное сообщение вместо ожидаемых ошибок базы."""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyError as error:
            print(f"Ошибка: таблица или столбец {error} не найден.")
        except ValueError as error:
            print(f"Ошибка валидации: {error}")
        except FileNotFoundError:
            print("Ошибка: файл данных не найден.")
        return None

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def confirm_action(action_name):
    """Запрашивает подтверждение перед изменением данных."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            answer = prompt.string(
                f'Вы уверены, что хотите выполнить "{action_name}"? [y/n]: '
            )
            if answer.strip().lower() != "y":
                print("Операция отменена.")
                return None
            return func(*args, **kwargs)

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator


def log_time(func):
    """Показывает время выполнения функции."""

    def wrapper(*args, **kwargs):
        started = time.monotonic()
        result = func(*args, **kwargs)
        elapsed = time.monotonic() - started
        print(f"Функция {func.__name__} выполнилась за {elapsed:.3f} секунд.")
        return result

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def create_cacher():
    """Создаёт кеш; метод clear сбрасывает его после изменения данных."""
    cache = {}

    def cache_result(key, value_func):
        if key not in cache:
            cache[key] = value_func()
        return cache[key]

    cache_result.clear = cache.clear
    return cache_result
