from sinsim.adapters.sources_to_pandapower import shunts

DECLARED = {"ALTAMIRA": (230.0,), "CHINU": (500.0, 110.0)}


def test_reactor_positive_capacitor_negative_per_pandapower_convention():
    reactors = [
        {
            "elementName": "ALTAMIRA REACTOR 25 MVAR",
            "subStation": "ALTAMIRA",
            "nominalCapacity": 25,
            "nomU": 230,
            "compensatorType": "Derivación",
            "elementState": "Operación",
        }
    ]
    capacitors = [
        {
            "elementName": "CHINU CONDENSADOR 5 MVAR",
            "subStation": "CHINU",
            "ratedCapacity": 5,
            "ratedVoltage": "110",
            "compensationType": "Derivación",
            "elementState": "Operación",
        },
        {
            "elementName": "SERIE",
            "subStation": "CHINU",
            "ratedCapacity": 50,
            "ratedVoltage": "500",
            "compensationType": "Serie",
            "elementState": "Operación",
        },
    ]
    df = shunts.parse_shunts(reactors, capacitors, DECLARED).set_index("shunt_id")
    assert df.loc["reactor:ALTAMIRA REACTOR 25 MVAR", "q_mvar"] == 25.0
    assert df.loc["reactor:ALTAMIRA REACTOR 25 MVAR", "bus"] == "ALTAMIRA|230"
    assert df.loc["capacitor:CHINU CONDENSADOR 5 MVAR", "q_mvar"] == -5.0
    assert bool(df.loc["capacitor:SERIE", "modeled"]) is False
    assert df.loc["capacitor:SERIE", "reason"] == "compensación serie"


def test_svc_statcom_modeled_but_sssc_not():
    data = [
        {
            "elementNames": "CHINU SVC",
            "substationName": "CHINU",
            "nomVoltage": "500",
            "inductiveRating": "150",
            "capacitiveRating": "250",
            "elementType": "SVC",
            "elementStateName": "Operación",
        },
        {
            "elementNames": "X SSSC",
            "substationName": "CHINU",
            "nomVoltage": "110",
            "inductiveRating": "0.793",
            "capacitiveRating": "0.793",
            "elementType": "SSSC",
            "elementStateName": "Operación",
        },
        {
            "elementNames": "SIN BARRA",
            "substationName": "NOEXISTE",
            "nomVoltage": "110",
            "inductiveRating": "1",
            "capacitiveRating": "1",
            "elementType": "STATCOM",
            "elementStateName": "Operación",
        },
    ]
    df = shunts.parse_svc_statcom(data, DECLARED)
    assert df.modeled.tolist() == [True, False, False]
    assert (
        df.iloc[0].bus == "CHINU|500" and df.iloc[0].cap_mvar == 250 and df.iloc[0].ind_mvar == 150
    )
    assert df.iloc[1].reason == "compensación serie (SSSC)"
    assert df.iloc[2].missing_params == ["bus"]
