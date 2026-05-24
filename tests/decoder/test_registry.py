import pytest

from drone_detector.decoder import registry


def test_dispatch_unknown_tag_raises():
    with pytest.raises(KeyError):
        registry.dispatch("not_a_protocol")


def test_dji_v2_registered():
    parser = registry.dispatch("dji_v2")
    assert callable(parser)


def test_astm_f3411_registered():
    parser = registry.dispatch("astm_f3411")
    assert callable(parser)
