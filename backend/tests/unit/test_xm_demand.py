import pytest

from sinsim.adapters.sources_to_pandapower import xm_demand
from sinsim.domain.errors import DomainError

VALUES = ",".join(str(i) for i in range(1, 25))


def test_normalize_concept_accepts_with_and_without_trailing_dot():
    assert xm_demand.normalize_concept("Ener.Act.") == "p_act_mw"
    assert xm_demand.normalize_concept("Ener.Reac") == "q_mvar"
    assert xm_demand.normalize_concept("Ener.Reac.") == "q_mvar"
    assert xm_demand.normalize_concept("Perd.PSTR") == "p_pstr_mw"
    assert xm_demand.normalize_concept("Perd.PSTR.") == "p_pstr_mw"
    assert xm_demand.normalize_concept("Otro") is None


def test_parse_synthetic_node_keeps_components_separately():
    text = "\n".join(
        [
            f"Uant,NODO1,110,Ener.Act.,{VALUES}",
            f"Uant,NODO1,110,Ener.Reac.,{VALUES}",
            f"Uant,NODO1,110,Perd.PSTR,{VALUES}",
        ]
    )
    df = xm_demand.parse_pron_barra(text)
    assert len(df) == 24
    row = df[df.period == 5].iloc[0]
    assert (row.p_act_mw, row.p_pstr_mw, row.q_mvar) == (5.0, 5.0, 5.0)
    assert row.ucp == "Uant" and row.node == "NODO1" and row.vn_kv == 110.0


def test_missing_concept_or_bad_row_is_schema_error():
    with pytest.raises(DomainError) as exc:
        xm_demand.parse_pron_barra(f"U,N,110,Ener.Act.,{VALUES}")
    assert exc.value.code == "XM_FILE_SCHEMA_CHANGED" and "no trae" in exc.value.detail
    with pytest.raises(DomainError):
        xm_demand.parse_pron_barra("U,N,110,Ener.Act.,1,2")
    with pytest.raises(DomainError):
        xm_demand.parse_pron_barra(f"U,N,110,Desconocido,{VALUES}")


def test_parse_real_pron_barra_1020(fixtures_dir):
    text = (fixtures_dir / "xm" / "PRON_BARRA1020.txt").read_text(
        encoding="utf-8", errors="replace"
    )
    df = xm_demand.parse_pron_barra(text, source="PRON_BARRA1020.txt")
    assert df.groupby(["node", "vn_kv"]).ngroups == 552
    assert (df.groupby(["node", "vn_kv"]).size() == 24).all()
    doncello = df[(df.node == "DONCELL1") & (df.period == 1)].iloc[0]
    assert doncello.p_act_mw == pytest.approx(12.7721394150)
    assert doncello.q_mvar == pytest.approx(0.8790314064)
    assert doncello.p_pstr_mw == pytest.approx(0.1944995850)
    assert doncello.vn_kv == 115.0 and doncello.ucp == "Uandaki"
