from llm.client import TokenUsageLogger

import logging


LOGGER = logging.getLogger(__name__)


def log_total_cost(token_usage_logger: TokenUsageLogger) -> None:
    total_cost = sum(
        cost
        for cost in token_usage_logger.request_costs
        if cost is not None
    )

    LOGGER.info(
        "Total reported cost: $%.8f USD | completed requests: %d | missing cost: %d",
        total_cost,
        len(token_usage_logger.request_costs),
        token_usage_logger.request_costs.count(None),
    )
