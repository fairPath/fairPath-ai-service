"""Comparison's existing error codes on the shared AI request boundary."""
from ai_errors import AiErrorRoute, AiRequestError

ComparisonError = AiRequestError


class ComparisonRoute(AiErrorRoute):
    invalid_request_code = "INVALID_COMPARISON_REQUEST"
