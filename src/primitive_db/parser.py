"""Разбор команд, значений и условий без выполнения пользовательского кода."""

import shlex


def tokenize(text):
    """Разделяет команду, сохраняя кавычки и знаки внутри строк."""
    tokens = []
    position = 0
    while position < len(text):
        char = text[position]
        if char.isspace():
            position += 1
            continue
        start = position
        if char in "\"'":
            quote = char
            position += 1
            while position < len(text):
                if text[position] == "\\" and quote == '"':
                    position += 2
                    continue
                if text[position] == quote:
                    break
                position += 1
            if position >= len(text):
                raise ValueError("Не закрыты кавычки.")
            position += 1
        elif char in "(),=":
            position += 1
        else:
            while position < len(text) and not text[position].isspace():
                if text[position] in "(),=\"'":
                    break
                position += 1
        tokens.append(text[start:position])
    return tokens


def parse_value(token):
    """Преобразует литерал в str, int или bool; строки требуют кавычек."""
    if token[:1] in ('"', "'"):
        return shlex.split(token)[0]
    if token.lower() in ("true", "false"):
        return token.lower() == "true"
    digits = token.lstrip("+-")
    if digits and digits.isdecimal() and token.count("+") + token.count("-") <= 1:
        return int(token)
    raise ValueError(f"Некорректное значение: {token}. Попробуйте снова.")


def parse_values(tokens):
    """Разбирает список значений в круглых скобках."""
    if isinstance(tokens, str):
        tokens = tokenize(tokens)
    if len(tokens) < 3 or tokens[0] != "(" or tokens[-1] != ")":
        raise ValueError("Ожидаются непустые values (значение, ...).")
    values = tokens[1:-1]
    if len(values) % 2 == 0 or any(item != "," for item in values[1::2]):
        raise ValueError("Разделяйте значения запятыми.")
    return [parse_value(item) for item in values[::2]]


def parse_where(tokens):
    """Разбирает одно условие равенства: столбец = значение."""
    if isinstance(tokens, str):
        tokens = tokenize(tokens)
    if len(tokens) != 3 or tokens[1] != "=" or not tokens[0].isidentifier():
        raise ValueError("Ожидается условие: столбец = значение.")
    return {tokens[0]: parse_value(tokens[2])}


def parse_set(tokens):
    """Разбирает присваивания, разделённые запятыми."""
    if isinstance(tokens, str):
        tokens = tokenize(tokens)
    if not tokens or len(tokens) % 4 != 3:
        raise ValueError("Ожидается set столбец = значение [, столбец = значение].")
    result = {}
    for start in range(0, len(tokens), 4):
        assignment = parse_where(tokens[start : start + 3])
        if result.keys() & assignment.keys():
            raise ValueError("Столбец повторяется в set.")
        result.update(assignment)
        if start + 3 < len(tokens) and tokens[start + 3] != ",":
            raise ValueError("Разделяйте присваивания запятыми.")
    return result


def parse_command(text):
    """Возвращает имя команды и разобранные аргументы."""
    tokens = tokenize(text)
    if not tokens:
        return "", ()
    command = tokens[0].lower()
    words = [token.lower() for token in tokens]
    if command in ("help", "exit", "list_tables") and len(tokens) == 1:
        return command, ()
    if command in ("drop_table", "info") and len(tokens) == 2:
        return command, (tokens[1],)
    if command == "create_table" and len(tokens) >= 3:
        return command, (tokens[1], tokens[2:])
    if command == "insert" and len(tokens) >= 7:
        if words[1] == "into" and words[3] == "values":
            return command, (tokens[2], parse_values(tokens[4:]))
    if command in ("select", "delete") and len(tokens) >= 3:
        if words[1] == "from":
            if command == "select" and len(tokens) == 3:
                return command, (tokens[2], None)
            if len(tokens) > 4 and words[3] == "where":
                return command, (tokens[2], parse_where(tokens[4:]))
    if command == "update" and len(tokens) > 7 and words[2] == "set":
        # where на позиции имени столбца допустим; разделитель идёт после значения.
        for index in range(6, len(tokens), 4):
            if words[index] == "where":
                return command, (
                    tokens[1],
                    parse_set(tokens[3:index]),
                    parse_where(tokens[index + 1 :]),
                )
    known = {
        "help",
        "exit",
        "list_tables",
        "drop_table",
        "info",
        "create_table",
        "insert",
        "select",
        "update",
        "delete",
    }
    if command not in known:
        return "unknown", (tokens[0],)
    raise ValueError(f"Некорректная команда {command}. Введите help для справки.")
