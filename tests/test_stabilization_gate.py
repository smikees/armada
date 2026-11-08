"""Performance evidence must fail closed, including missing or nonfinite observations."""
import copy
import pytest
from tools.stabilization_gate import PERFORMANCE_BUDGETS, validate_performance


def evidence():
    return {**{name: {'p95_ms': ceiling / 2} for name, ceiling in PERFORMANCE_BUDGETS.items()},
            'realm_cold_ms': 500}


def test_valid_measurements_pass_without_mutating_evidence():
    report = evidence()
    before = copy.deepcopy(report)
    validate_performance(report)
    assert report == before


@pytest.mark.parametrize('name', list(PERFORMANCE_BUDGETS))
@pytest.mark.parametrize('value', [None, True, -1, float('nan'), float('inf'), 10001])
def test_missing_invalid_and_regressed_warm_observations_fail(name, value):
    report = evidence()
    report[name] = {'p95_ms': value}
    with pytest.raises(ValueError, match=name):
        validate_performance(report)


@pytest.mark.parametrize('value', [None, True, -1, float('nan'), 10001])
def test_cold_evidence_is_required_and_bounded(value):
    report = evidence()
    report['realm_cold_ms'] = value
    with pytest.raises(ValueError, match='Cold'):
        validate_performance(report)


def test_missing_warm_series_is_not_treated_as_zero():
    report = evidence()
    del report['four_windows']
    with pytest.raises(ValueError, match='four_windows'):
        validate_performance(report)


def test_early_dependency_failure_replaces_previous_success(tmp_path, monkeypatch):
    import json
    import os
    from tools import release_gate, stabilization_gate
    if os.name != 'nt':
        pytest.skip('Complete gate is Windows-only')
    output = tmp_path / 'summary.json'
    output.write_text('{"ok":true}')
    def fail():
        raise SystemExit('synthetic dependency failure')
    monkeypatch.setattr(release_gate, 'verify_dependencies', fail)
    with pytest.raises(SystemExit, match='synthetic'):
        stabilization_gate.run(output)
    assert json.loads(output.read_text())['ok'] is False
