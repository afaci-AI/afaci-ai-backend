"""Граница транзакции: фиксирует при успехе, откатывает и пробрасывает при сбое."""

import unittest

from core.transaction import transaction


class FakeUnit:
    def __init__(self, commit_error=None):
        self.calls = []
        self.commit_error = commit_error

    async def commit(self):
        if self.commit_error:
            raise self.commit_error
        self.calls.append("commit")

    async def rollback(self):
        self.calls.append("rollback")


class TransactionBoundary(unittest.IsolatedAsyncioTestCase):
    async def test_success_commits_only(self):
        unit = FakeUnit()
        async with transaction(unit):
            pass
        self.assertEqual(unit.calls, ["commit"])

    async def test_failure_in_block_rolls_back_and_reraises(self):
        unit = FakeUnit()
        with self.assertRaises(ValueError):
            async with transaction(unit):
                raise ValueError("boom")
        self.assertEqual(unit.calls, ["rollback"])

    async def test_failed_commit_rolls_back(self):
        unit = FakeUnit(commit_error=RuntimeError("fk"))
        with self.assertRaises(RuntimeError):
            async with transaction(unit):
                pass
        self.assertEqual(unit.calls, ["rollback"])


if __name__ == "__main__":
    unittest.main()
