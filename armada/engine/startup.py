"""Failures before a provider turn starts, with no business-job replay."""
from .base import RunResult, Usage


def failed(reason, *, code="provider_startup", model="", cancelled=False):
    return RunResult(ok=False, error=reason, model=model, cancelled=cancelled,
                     usage=Usage(input=0, output=0, cost_usd=0),
                     raw={"startup_failure": {"code": code, "reason": reason}})
