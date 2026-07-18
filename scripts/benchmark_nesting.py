"""Development-only deterministic benchmark and profiler for Debbie nesting."""

from __future__ import annotations

import argparse
import cProfile
from dataclasses import dataclass
import platform
import pstats
import sys
from time import perf_counter
from unittest.mock import patch

import debbie.nesting.candidates as candidate_module
import debbie.nesting.solver as solver_module
from debbie.domain import (
    DemandItem,
    DemandItemId,
    Dimensions,
    Orientation,
    PartType,
    PartTypeId,
    ProcessProfile,
    StockInstance,
    StockInstanceId,
    StockSpecification,
    StockSpecificationId,
    Trim,
    Work,
    WorkId,
)
from debbie.nesting import LeftToRightNestingSolver, nest_work


@dataclass(slots=True)
class BenchmarkCounters:
    candidates_generated: int = 0
    candidate_placements_tested: int = 0
    incremental_geometry_validations: int = 0
    complete_geometry_validations: int = 0
    stock_simulations: int = 0
    maximum_candidates_for_one_placement: int = 0

    @property
    def total_geometry_validations(self) -> int:
        return self.incremental_geometry_validations + self.complete_geometry_validations


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    scenario: str
    size: int
    runtime_seconds: float
    requested_parts: int
    opened_sheets: int
    result_status: str
    placed_parts: int
    unplaced_parts: int
    counters: BenchmarkCounters


def _build_work(
    *,
    name: str,
    parts: tuple[tuple[str, float, float, int], ...],
    stock_length: float,
    stock_width: float,
    stock_quantity: int,
    process: ProcessProfile,
) -> Work:
    work_id = WorkId(f"benchmark-{name}")
    part_types = tuple(
        PartType(
            PartTypeId(identifier),
            identifier,
            Dimensions(length, width),
        )
        for identifier, length, width, _ in parts
    )
    demand_items = tuple(
        DemandItem(
            DemandItemId(f"demand-{identifier}"),
            work_id,
            PartTypeId(identifier),
            quantity,
        )
        for identifier, _, _, quantity in parts
    )
    specification = StockSpecification(
        StockSpecificationId("benchmark-stock"),
        "Benchmark Stock",
        Dimensions(stock_length, stock_width),
    )
    stock_instances = tuple(
        StockInstance(
            StockInstanceId(f"benchmark-stock-{sequence}"),
            work_id,
            specification.id,
            sequence,
        )
        for sequence in range(1, stock_quantity + 1)
    )
    return Work.from_inputs(
        id=work_id,
        name=name,
        batch_multiplier=1,
        process_profile=process,
        part_types=part_types,
        demand_items=demand_items,
        stock_specifications=(specification,),
        stock_instances=stock_instances,
    )


def simple_fixture(size: int) -> Work:
    return _build_work(
        name=f"simple-{size}",
        parts=(("repeated-rectangle", 10.0, 10.0, size),),
        stock_length=107.0,
        stock_width=107.0,
        stock_quantity=3,
        process=ProcessProfile(
            minimum_part_clearance=0.25,
            trim=Trim(left=1.0, right=1.0, top=1.0, bottom=1.0),
        ),
    )


def mixed_fixture(size: int) -> Work:
    dimensions = (
        ("mixed-a", 18.0, 11.0),
        ("mixed-b", 13.0, 9.0),
        ("mixed-c", 7.0, 5.0),
        ("mixed-d", 21.0, 8.0),
        ("mixed-e", 12.0, 12.0),
    )
    base, remainder = divmod(size, len(dimensions))
    parts = tuple(
        (identifier, length, width, base + (1 if index < remainder else 0))
        for index, (identifier, length, width) in enumerate(dimensions)
    )
    return _build_work(
        name=f"mixed-{size}",
        parts=parts,
        stock_length=124.0,
        stock_width=104.0,
        stock_quantity=5,
        process=ProcessProfile(
            minimum_part_clearance=0.75,
            trim=Trim(left=2.0, right=2.0, top=2.0, bottom=2.0),
        ),
    )


def dense_fixture(size: int) -> Work:
    parts = tuple(
        (
            f"dense-{index:03d}",
            5.0 + (index % 11) * 0.7,
            4.0 + ((index * 7) % 13) * 0.5,
            1,
        )
        for index in range(size)
    )
    return _build_work(
        name=f"dense-{size}",
        parts=parts,
        stock_length=104.0,
        stock_width=104.0,
        stock_quantity=4,
        process=ProcessProfile(
            minimum_part_clearance=0.4,
            trim=Trim(left=2.0, right=2.0, top=2.0, bottom=2.0),
        ),
    )


def run_benchmark(
    scenario: str, size: int, work: Work, *, profile_run: bool, profile_lines: int
) -> BenchmarkResult:
    counters = BenchmarkCounters()
    current_search_count = 0
    original_iter = candidate_module.iter_placement_candidates
    original_incremental = candidate_module.candidate_satisfies_existing_geometry
    original_search = solver_module.first_valid_placement_candidate
    original_complete = solver_module.validate_layout_geometry
    original_simulation = LeftToRightNestingSolver._simulate_sheet

    def tracked_iter(*args, **kwargs):
        for candidate in original_iter(*args, **kwargs):
            counters.candidates_generated += 1
            yield candidate

    def tracked_incremental(*args, **kwargs):
        nonlocal current_search_count
        counters.candidate_placements_tested += 1
        counters.incremental_geometry_validations += 1
        current_search_count += 1
        return original_incremental(*args, **kwargs)

    def tracked_search(*args, **kwargs):
        nonlocal current_search_count
        current_search_count = 0
        result = original_search(*args, **kwargs)
        counters.maximum_candidates_for_one_placement = max(
            counters.maximum_candidates_for_one_placement, current_search_count
        )
        return result

    def tracked_complete(*args, **kwargs):
        counters.complete_geometry_validations += 1
        return original_complete(*args, **kwargs)

    def tracked_simulation(self, *args, **kwargs):
        counters.stock_simulations += 1
        return original_simulation(self, *args, **kwargs)

    profiler = cProfile.Profile() if profile_run else None
    with (
        patch.object(candidate_module, "iter_placement_candidates", tracked_iter),
        patch.object(
            candidate_module,
            "candidate_satisfies_existing_geometry",
            tracked_incremental,
        ),
        patch.object(solver_module, "first_valid_placement_candidate", tracked_search),
        patch.object(solver_module, "validate_layout_geometry", tracked_complete),
        patch.object(LeftToRightNestingSolver, "_simulate_sheet", tracked_simulation),
    ):
        started = perf_counter()
        if profiler is not None:
            profiler.enable()
        result = nest_work(work)
        if profiler is not None:
            profiler.disable()
        runtime = perf_counter() - started

    if profiler is not None:
        print(f"\nPROFILE scenario={scenario} size={size}")
        pstats.Stats(profiler).strip_dirs().sort_stats("cumulative").print_stats(
            profile_lines
        )

    return BenchmarkResult(
        scenario=scenario,
        size=size,
        runtime_seconds=runtime,
        requested_parts=result.requested_part_count,
        opened_sheets=len(result.layouts),
        result_status=result.status.value,
        placed_parts=result.placed_part_count,
        unplaced_parts=sum(item.remaining_quantity for item in result.unplaced_demand),
        counters=counters,
    )


def _print_result(result: BenchmarkResult) -> None:
    counters = result.counters
    print(
        f"scenario={result.scenario} size={result.size} "
        f"runtime_seconds={result.runtime_seconds:.6f} "
        f"parts_processed={result.requested_parts} "
        f"opened_sheets={result.opened_sheets} "
        f"candidates_generated={counters.candidates_generated} "
        f"candidate_placements_tested={counters.candidate_placements_tested} "
        f"geometry_validations={counters.total_geometry_validations} "
        f"incremental_validations={counters.incremental_geometry_validations} "
        f"complete_validations={counters.complete_geometry_validations} "
        f"stock_simulations={counters.stock_simulations} "
        f"max_candidates_one_placement={counters.maximum_candidates_for_one_placement} "
        f"status={result.result_status} placed={result.placed_parts} "
        f"unplaced={result.unplaced_parts}"
    )


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario", choices=("all", "simple", "mixed", "dense"), default="all"
    )
    parser.add_argument("--size", type=int, help="override the selected scenario size")
    parser.add_argument("--profile", action="store_true", help="print cProfile output")
    parser.add_argument("--profile-lines", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if args.size is not None and args.size <= 0:
        raise SystemExit("--size must be a positive integer")
    print(f"python={sys.version.split()[0]} platform={platform.platform()}")
    if args.scenario == "all":
        fixtures = (
            ("simple", 25, simple_fixture(25)),
            ("simple", 50, simple_fixture(50)),
            ("simple", 100, simple_fixture(100)),
            ("mixed", 50, mixed_fixture(50)),
            ("mixed", 100, mixed_fixture(100)),
            ("dense", 60, dense_fixture(60)),
        )
    else:
        default_size = {"simple": 100, "mixed": 100, "dense": 60}[args.scenario]
        size = args.size or default_size
        factory = {
            "simple": simple_fixture,
            "mixed": mixed_fixture,
            "dense": dense_fixture,
        }[args.scenario]
        fixtures = ((args.scenario, size, factory(size)),)

    for scenario, size, work in fixtures:
        _print_result(
            run_benchmark(
                scenario,
                size,
                work,
                profile_run=args.profile,
                profile_lines=args.profile_lines,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
