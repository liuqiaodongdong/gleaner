# tests/test_acq_mcp_intl.py
import inspect
import acq_mcp


def test_run_collect_has_script_param():
    assert "script" in inspect.signature(acq_mcp._run_collect).parameters


def test_intl_collect_registered():
    assert hasattr(acq_mcp, "intl_collect")


def test_intl_collect_no_return_annotation():
    assert inspect.signature(acq_mcp.intl_collect).return_annotation is inspect.Signature.empty


def test_els_collect_registered_via_intl_module():
    assert hasattr(acq_mcp, "els_collect")
