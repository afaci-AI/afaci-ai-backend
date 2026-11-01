"""Opt-in migration check using only an explicitly supplied disposable database.

REFERENCE_MIGRATION_TEST_URL=postgresql+asyncpg://... python -m unittest discover \
    -s tests -p test_reference_source_migration.py -v

Never points to DATABASE_URL, imports the app session, or reads .env.
"""

import importlib.util
import os
import unittest
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.ext.asyncio import create_async_engine


@unittest.skipUnless(
    os.getenv("REFERENCE_MIGRATION_TEST_URL"), "disposable DB not supplied"
)
class ReferenceSourceMigrationChecks(unittest.IsolatedAsyncioTestCase):
    async def test_additive_migration_preserves_reference_values(self):
        await self.check_upgrade(seed_columns=False)

    async def test_seed_columns_before_migration_preserve_values(self):
        await self.check_upgrade(seed_columns=True)

    async def check_upgrade(self, *, seed_columns: bool):
        engine = create_async_engine(os.environ["REFERENCE_MIGRATION_TEST_URL"])
        schema_name = "reference_source_test_" + uuid4().hex
        migration_path = (
            Path(__file__).parents[1]
            / "alembic/versions/e5f6a7b8c9d0_add_reference_sources.py"
        )
        spec = importlib.util.spec_from_file_location(
            "reference_migration", migration_path
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        async with engine.begin() as connection:
            await connection.execute(sa.text(f'CREATE SCHEMA "{schema_name}"'))
            await connection.execute(
                sa.text(f'SET LOCAL search_path TO "{schema_name}"')
            )
            await connection.execute(
                sa.text("""
                CREATE TABLE reference_proteins (
                    id uuid PRIMARY KEY, name varchar UNIQUE NOT NULL, year integer,
                    is_default boolean NOT NULL DEFAULT false, description text
                )
            """)
            )
            await connection.execute(
                sa.text("""
                CREATE TABLE reference_protein_values (
                    id uuid PRIMARY KEY, reference_protein_id uuid REFERENCES reference_proteins,
                    amino_acid varchar NOT NULL, value double precision NOT NULL
                )
            """)
            )
            if seed_columns:
                # Reproduce the source columns added by running the seed first.
                for name, sql_type in (
                    ("source_title", "text"),
                    ("source_authors", "text"),
                    ("source_year", "integer"),
                    ("source_location", "text"),
                    ("source_url", "text"),
                    ("source_pdf_filename", "varchar"),
                ):
                    await connection.execute(
                        sa.text(
                            f"ALTER TABLE reference_proteins ADD COLUMN {name} {sql_type}"
                        )
                    )
            for index, year in enumerate((1973, 1985, 1991)):
                ref_id = uuid4()
                await connection.execute(
                    sa.text("""
                    INSERT INTO reference_proteins (id, name, year, is_default, description)
                    VALUES (:id, :name, :year, :default, 'Old description')
                """),
                    {
                        "id": ref_id,
                        "name": f"ФАО/ВОЗ {year}",
                        "year": year,
                        "default": index == 0,
                    },
                )
                await connection.execute(
                    sa.text("""
                    INSERT INTO reference_protein_values VALUES (:id, :ref, 'ЛИЗ', :value)
                """),
                    {
                        "id": uuid4(),
                        "ref": ref_id,
                        "value": 5.5 if year == 1973 else 5.8,
                    },
                )
            before = (
                await connection.execute(
                    sa.text("SELECT * FROM reference_protein_values ORDER BY id")
                )
            ).all()

            def upgrade(sync_connection):
                context = MigrationContext.configure(sync_connection)
                with Operations.context(context):
                    migration.upgrade()

            await connection.run_sync(upgrade)
            after = (
                await connection.execute(
                    sa.text("SELECT * FROM reference_protein_values ORDER BY id")
                )
            ).all()
            self.assertEqual(before, after)
            refs = (
                (
                    await connection.execute(
                        sa.text(
                            "SELECT name, source_title, source_year, source_url, source_pdf_filename, description FROM reference_proteins ORDER BY year"
                        )
                    )
                )
                .mappings()
                .all()
            )
            self.assertEqual(len(refs), 3)
            for row in refs:
                self.assertTrue(row["source_title"])
                self.assertTrue(row["source_url"].startswith("https://"))
                self.assertIsNone(row["source_pdf_filename"])
            self.assertNotIn("яичного", refs[0]["description"])
            await connection.execute(sa.text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        await engine.dispose()
