"""Execute SELECT queries on small, curated SQLite fixtures and compare results."""
import re
import sqlite3
import time
from collections import Counter


class QueryError(ValueError):
    """The generated query was invalid or exceeded the supported execution limits."""


def run_query(case, rows, query):
    if not re.match(r"\s*(SELECT|WITH)\b", query, re.I):
        raise QueryError("Only SELECT queries and read-only WITH queries are supported")
    table = case["table"]
    if not re.fullmatch(r"[a-zA-Z_]\w*", table):
        raise ValueError("Invalid fixture table name")
    connection = sqlite3.connect(":memory:")
    try:
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1_000_000)
        connection.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 16_000)
        connection.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
        # Schema and rows are reviewed fixture definitions, never model output.
        connection.execute(case["schema"])
        if rows:
            placeholders = ",".join("?" for _ in rows[0])
            connection.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', rows)
        connection.commit()
        connection.execute("PRAGMA query_only=ON")
        functions = {"count", "sum", "avg", "min", "max", "lower", "upper", "length", "coalesce", "ifnull", "nullif", "round", "abs"}

        def authorise(action, arg1, arg2, database, trigger):
            if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE):
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_READ and arg1 == table:
                # COUNT(*) reads the table with an empty column and no database name.
                if database == "main" or (database is None and arg2 == ""):
                    return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in functions:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY

        steps = 0
        deadline = time.monotonic() + 0.25

        def interrupted():
            nonlocal steps
            steps += 1_000
            return steps > 100_000 or time.monotonic() > deadline

        connection.set_authorizer(authorise)
        connection.set_progress_handler(interrupted, 1_000)
        # execute() accepts one statement, unlike executescript().
        cursor = connection.execute(query)
        result = cursor.fetchmany(1_001)
        if len(result) > 1_000:
            raise QueryError("Query exceeded the 1000-row limit")
        return {"rows": [list(row) for row in result], "columns": len(cursor.description)}
    except sqlite3.Error as error:
        raise QueryError(str(error)) from error
    finally:
        connection.close()


def rows_equal(left, right, ordered):
    if ordered:
        return left == right
    # A set would lose duplicates and incorrectly accept DISTINCT queries.
    return Counter(map(tuple, left)) == Counter(map(tuple, right))


def grade_query(case, query):
    outcomes = []
    if not case["fixtures"]:
        raise ValueError("A case must have at least one fixture")
    for fixture in case["fixtures"]:
        try:
            reference = run_query(case, fixture["rows"], case["reference_sql"])
        except QueryError as error:
            raise ValueError(f"Invalid reference query in {fixture['name']}: {error}") from error
        if not rows_equal(reference["rows"], fixture["expected"], case["ordered"]):
            raise ValueError(f"Fixture {fixture['name']} disagrees with its reference query")
        outcome = {"name": fixture["name"], "expected": reference["rows"]}
        try:
            actual = run_query(case, fixture["rows"], query)
            outcome["actual"] = actual["rows"]
            outcome["passed"] = actual["columns"] == reference["columns"] and rows_equal(
                actual["rows"], reference["rows"], case["ordered"],
            )
        except QueryError as error:
            outcome.update({"passed": False, "error": str(error)})
        outcomes.append(outcome)
    return {"passed": all(row["passed"] for row in outcomes), "fixtures": outcomes}
