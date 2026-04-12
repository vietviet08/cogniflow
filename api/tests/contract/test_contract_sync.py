from scripts.check_contract_sync import check_api_spec_contract, check_schema_contract


def test_schema_contract_sync_passes():
    assert check_schema_contract() == []


def test_api_spec_contract_sync_passes():
    assert check_api_spec_contract() == []
