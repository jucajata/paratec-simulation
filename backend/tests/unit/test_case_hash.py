from datetime import date

from sinsim.domain.case_hash import canonical_json, case_id_for
from sinsim.domain.entities import CaseInputs


def inputs(**overrides):
    base = dict(
        snapshot_date=date(2026, 10, 20),
        dispatch_date=date(2026, 10, 20),
        period=19,
        snapshot_manifest_sha256="a" * 64,
        equivalences_sha256="b" * 64,
        config_sha256="c" * 64,
        sinsim_version="0.1.0",
    )
    base.update(overrides)
    return CaseInputs(**base)


def test_hash_is_deterministic_and_64_hex():
    a, b = case_id_for(inputs()), case_id_for(inputs())
    assert a == b and len(a) == 64 and int(a, 16) >= 0


def test_canonical_json_has_sorted_keys_and_no_spaces():
    text = canonical_json(inputs())
    assert text.startswith('{"config_sha256":')
    assert " " not in text and "\n" not in text


def test_any_input_change_changes_the_id():
    base = case_id_for(inputs())
    assert case_id_for(inputs(period=20)) != base
    assert case_id_for(inputs(config_sha256="d" * 64)) != base
    assert case_id_for(inputs(equivalences_sha256="d" * 64)) != base
    assert case_id_for(inputs(snapshot_manifest_sha256="d" * 64)) != base
    assert case_id_for(inputs(dispatch_date=date(2026, 10, 21))) != base
    assert case_id_for(inputs(sinsim_version="0.2.0")) != base
