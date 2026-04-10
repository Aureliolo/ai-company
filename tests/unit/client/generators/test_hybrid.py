"""Unit tests for HybridGenerator."""

import pytest

from synthorg.client.generators import HybridGenerator, ProceduralGenerator
from synthorg.client.models import GenerationContext, TaskRequirement
from synthorg.client.protocols import RequirementGenerator

pytestmark = pytest.mark.unit


class _StaticGenerator:
    """Test double that always returns a fixed requirement."""

    def __init__(self, *, title: str) -> None:
        self._title = title

    async def generate(self, context: GenerationContext) -> tuple[TaskRequirement, ...]:
        return tuple(
            TaskRequirement(
                title=self._title,
                description=f"desc for {self._title}",
            )
            for _ in range(context.count)
        )


def _ctx(count: int = 3) -> GenerationContext:
    return GenerationContext(
        project_id="proj-1",
        domain="backend",
        count=count,
    )


class TestHybridGeneratorConstructor:
    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            HybridGenerator(generators=())

    def test_rejects_negative_weight(self) -> None:
        a = _StaticGenerator(title="A")
        with pytest.raises(ValueError, match="non-negative"):
            HybridGenerator(generators=((a, -1.0),))

    def test_rejects_zero_total_weight(self) -> None:
        a = _StaticGenerator(title="A")
        with pytest.raises(ValueError, match="sum of generator weights"):
            HybridGenerator(generators=((a, 0.0),))

    def test_protocol_compatible(self) -> None:
        gen = HybridGenerator(
            generators=((_StaticGenerator(title="A"), 1.0),),
        )
        assert isinstance(gen, RequirementGenerator)


class TestHybridGeneratorGenerate:
    async def test_uses_single_delegate(self) -> None:
        gen = HybridGenerator(
            generators=((_StaticGenerator(title="Only"), 1.0),),
            seed=1,
        )
        result = await gen.generate(_ctx(count=4))
        assert len(result) == 4
        assert all(r.title == "Only" for r in result)

    async def test_weighted_distribution(self) -> None:
        a = _StaticGenerator(title="A")
        b = _StaticGenerator(title="B")
        gen = HybridGenerator(
            generators=((a, 9.0), (b, 1.0)),
            seed=42,
        )
        result = await gen.generate(_ctx(count=100))
        a_count = sum(1 for r in result if r.title == "A")
        # Heavy A weight should produce majority A
        assert a_count >= 70

    async def test_deterministic_with_seed(self) -> None:
        a = _StaticGenerator(title="A")
        b = _StaticGenerator(title="B")
        gen_a = HybridGenerator(generators=((a, 1.0), (b, 1.0)), seed=123)
        gen_b = HybridGenerator(generators=((a, 1.0), (b, 1.0)), seed=123)
        result_a = await gen_a.generate(_ctx(count=10))
        result_b = await gen_b.generate(_ctx(count=10))
        assert [r.title for r in result_a] == [r.title for r in result_b]

    async def test_composes_with_real_generator(self) -> None:
        procedural = ProceduralGenerator(seed=1)
        static = _StaticGenerator(title="Static")
        gen = HybridGenerator(
            generators=((procedural, 1.0), (static, 1.0)),
            seed=7,
        )
        result = await gen.generate(_ctx(count=5))
        assert len(result) == 5
