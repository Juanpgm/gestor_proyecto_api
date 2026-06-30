"""Run the repository contract against the in-memory fakes (no DB needed)."""

import pytest

from .fakes import (
    InMemoryIntervencionesRepository,
    InMemoryUnidadesProyectoRepository,
)
from .repo_contract import IntervencionesContract, UnidadesProyectoContract

pytestmark = pytest.mark.contract


class TestFakeUnidadesProyecto(UnidadesProyectoContract):
    @pytest.fixture
    def up_repo(self):
        return InMemoryUnidadesProyectoRepository()


class TestFakeIntervenciones(IntervencionesContract):
    @pytest.fixture
    def int_repo(self):
        return InMemoryIntervencionesRepository()
