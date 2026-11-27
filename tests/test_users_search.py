"""Поиск пользователей выполняет хранилище (SQL), сервис только передаёт параметры."""

import unittest
from unittest.mock import AsyncMock, Mock

from features.users.app.service import UserService
from features.users.infra.sql_repo import SqlUserRepository, _search_clause
from tests.account_fakes import FakeAccounts, account_row


class ServiceDelegatesSearch(unittest.IsolatedAsyncioTestCase):
    async def test_service_passes_role_and_search_to_repository(self):
        repo = FakeAccounts(
            account_row(email="anna@example.com", name="Анна", role="admin"),
            account_row(email="boris@example.com", name="Борис", role="viewer"),
        )
        service = UserService(repo, hasher=None, audit=None)
        found = await service.list("admin", "АННА")
        self.assertEqual(repo.list_calls, [{"role": "admin", "search": "АННА"}])
        self.assertEqual([u.name for u in found], ["Анна"])


class SqlSearchClause(unittest.TestCase):
    def test_matches_email_or_name_with_folded_cyrillic_needle(self):
        clause = _search_clause(" Ёлка ")
        sql = str(clause)
        self.assertIn("users.email", sql)
        self.assertIn("users.name", sql)
        self.assertIn(" OR ", sql)
        values = {p.key: p.value for p in clause._bindparams.values()}
        self.assertEqual(values["ue"], "%елка%")
        self.assertEqual(values["un"], "%елка%")

    def test_like_wildcards_in_query_are_escaped(self):
        values = {p.key: p.value for p in _search_clause("a_b%")._bindparams.values()}
        self.assertEqual(values["ue"], "%a\\_b\\%%")

    def test_blank_query_does_not_filter(self):
        self.assertEqual(str(_search_clause("   ")), "TRUE")


class SqlRepositoryList(unittest.IsolatedAsyncioTestCase):
    async def test_search_becomes_where_clause_of_the_query(self):
        result = Mock()
        result.scalars.return_value.all.return_value = []
        db = Mock(execute=AsyncMock(return_value=result))
        await SqlUserRepository(db).list(role="admin", search="Анна")
        sql = str(db.execute.await_args.args[0])
        self.assertIn("users.role = :role_1", sql)
        self.assertIn("users.email", sql)
        self.assertIn("ORDER BY users.created_at DESC", sql)


if __name__ == "__main__":
    unittest.main()
