import inspect
import acq_mcp


def test_els_collect_registered():
    assert hasattr(acq_mcp, "els_collect")


def test_els_collect_no_return_annotation():
    assert inspect.signature(acq_mcp.els_collect).return_annotation is inspect.Signature.empty


def test_els_collect_params_annotated():
    params = inspect.signature(acq_mcp.els_collect).parameters
    assert params["query"].annotation is str
    assert params["tier"].annotation is str
    assert "year_from" in params and "per_journal" in params
