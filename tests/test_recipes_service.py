"""Recipe use-cases and ranking rules against in-memory fakes (no database)."""

import unittest
from uuid import uuid4

from core.errors import BadRequestError, NotFoundError
from features.recipes.app import ItemData, RecipeChanges, RecipeService
from features.recipes.domain import (
    RankingWeights,
    Recipe,
    RecipeItem,
    RecipeMetrics,
    normalize,
    rank_recipes,
)

USER = uuid4()
REPORT = {
    "quality": {"bc": 80.0, "kras": 20.0, "U": 0.7, "G": 1.5},
    "energy_kcal": 200.0,
    "c_min": {"name": "ЛИЗ", "score": 80.0},
}


class FakeCalculator:
    def __init__(self):
        self.calls = []

    async def compute(self, reference_protein_id, items):
        self.calls.append((reference_protein_id, items))
        return REPORT


class FakeRepo:
    def __init__(self, recipes=(), groups=()):
        self.recipes = {r.id: r for r in recipes}
        self.groups = set(groups)
        self.created = []
        self.saved = []

    async def group_exists(self, user_id, group_id):
        return group_id in self.groups

    async def get_recipe(self, user_id, recipe_id, *, with_items):
        return self.recipes.get(recipe_id)

    async def create_recipe(self, user_id, recipe, new_group_name):
        self.created.append((recipe, new_group_name))
        return recipe

    async def save_recipe(self, user_id, recipe):
        self.saved.append(recipe)
        return recipe

    async def find_recipes(self, user_id, ids):
        return [self.recipes[i] for i in ids if i in self.recipes]

    async def group_names(self, user_id):
        return {}


def recipe(**metrics):
    return Recipe(
        id=uuid4(),
        name="r",
        reference_protein_id=uuid4(),
        metrics=RecipeMetrics(**metrics),
        items=[RecipeItem(uuid4(), 60.0, 1), RecipeItem(uuid4(), 40.0, 0)],
    )


def items():
    return [ItemData(uuid4(), 60.0, 100.0), ItemData(uuid4(), 40.0)]


class RankingTests(unittest.TestCase):
    def test_normalize_directions_and_flat_sample(self):
        self.assertEqual(normalize([1.0, 3.0], True), [0.0, 1.0])
        self.assertEqual(normalize([1.0, 3.0], False), [1.0, 0.0])
        self.assertEqual(normalize([2.0, 2.0], True), [1.0, 1.0])
        self.assertEqual(normalize([None, None], True), [0.0, 0.0])

    def test_better_metrics_rank_first(self):
        weak = recipe(bc=50.0, kras=40.0, u=0.4, g=3.0)
        strong = recipe(bc=90.0, kras=5.0, u=0.9, g=0.5)
        result = rank_recipes([weak, strong], {}, RankingWeights())
        self.assertEqual(result["winner"], str(strong.id))
        self.assertEqual([r["rank"] for r in result["ranking"]], [1, 2])
        self.assertAlmostEqual(
            sum(v for k, v in result["weights"].items() if k != "v"), 1
        )


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_draft_is_saved_without_calculation(self):
        calc, repo = FakeCalculator(), FakeRepo()
        service = RecipeService(repo, calc)
        await service.create_recipe(
            USER,
            name=" черновик ",
            reference_protein_id=uuid4(),
            items=items(),
            draft=True,
            group_id=None,
            new_group_name=None,
        )
        saved, _ = repo.created[0]
        self.assertEqual(calc.calls, [])
        self.assertEqual(saved.name, "черновик")
        self.assertIsNone(saved.metrics.bc)
        self.assertEqual([i.sort_order for i in saved.items], [0, 1])

    async def test_create_stores_metrics_and_checks_group(self):
        calc, repo = FakeCalculator(), FakeRepo()
        service = RecipeService(repo, calc)
        with self.assertRaises(NotFoundError) as caught:
            await service.create_recipe(
                USER,
                name="r",
                reference_protein_id=uuid4(),
                items=items(),
                draft=False,
                group_id=uuid4(),
                new_group_name=None,
            )
        self.assertEqual(caught.exception.detail, "Группа не найдена.")
        await service.create_recipe(
            USER,
            name="r",
            reference_protein_id=uuid4(),
            items=items(),
            draft=False,
            group_id=uuid4(),
            new_group_name="  новая ",
        )
        saved, new_group = repo.created[0]
        self.assertEqual(new_group, "новая")
        self.assertIsNone(saved.group_id)
        self.assertEqual((saved.metrics.bc, saved.metrics.u), (80.0, 0.7))

    async def test_reference_change_recalculates_from_sorted_items(self):
        existing = recipe(bc=1.0)
        calc, repo = FakeCalculator(), FakeRepo([existing])
        service = RecipeService(repo, calc)
        new_ref = uuid4()
        await service.update_recipe(
            USER,
            existing.id,
            RecipeChanges(
                reference_protein_id=new_ref, provided={"reference_protein_id"}
            ),
        )
        ref, computed = calc.calls[0]
        self.assertEqual(ref, new_ref)
        self.assertEqual([c["amount_g"] for c in computed], [40.0, 60.0])
        self.assertEqual(existing.metrics.bc, 80.0)
        self.assertFalse(existing.items_changed)

    async def test_draft_update_clears_metrics_and_replaces_items(self):
        existing = recipe(bc=1.0, kras=2.0)
        calc, repo = FakeCalculator(), FakeRepo([existing])
        service = RecipeService(repo, calc)
        await service.update_recipe(
            USER,
            existing.id,
            RecipeChanges(items=items(), draft=True, provided={"items", "draft"}),
        )
        self.assertEqual(calc.calls, [])
        self.assertIsNone(existing.metrics.bc)
        self.assertTrue(existing.items_changed)

    async def test_unknown_recipe_and_empty_ranking(self):
        service = RecipeService(FakeRepo(), FakeCalculator())
        with self.assertRaises(NotFoundError):
            await service.get_recipe(USER, uuid4())
        with self.assertRaises(BadRequestError):
            await service.rank(USER, [], RankingWeights())
        with self.assertRaises(NotFoundError) as caught:
            await service.rank(USER, [uuid4()], RankingWeights())
        self.assertEqual(caught.exception.detail, "Некоторые рецептуры не найдены.")


if __name__ == "__main__":
    unittest.main()
