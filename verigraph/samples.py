"""Curated example passages used to demo the workflow without typing.

The two documents below intentionally share entities (an organisation, a
product and a person) so that a question can only be answered by joining
facts that live in *different* documents through the graph.
"""

from __future__ import annotations

SAMPLE_DOCUMENTS: dict[str, str] = {
    "Aster Systems - company background": (
        "Aster Systems is a climate analytics company founded in 2018 by "
        "Priya Anand. Its flagship product, Cirrus, is a weather-risk "
        "scoring platform adopted by insurance underwriters. Aster Systems "
        "raised a 15 million dollar Series B round from Northgate Capital "
        "in 2021. Priya Anand previously ran data science at Meridian "
        "Weather, a forecasting bureau in Oslo."
    ),
    "Fernwood Insurance - deployment case": (
        "Fernwood Insurance, a commercial insurer headquartered in Zurich, "
        "became an early Cirrus customer in 2022 to price storm damage "
        "cover. The rollout across Fernwood's underwriting desks was "
        "coordinated by Elias Wolf, who worked directly with Cirrus product "
        "lead Priya Anand. Fernwood reports that the platform cut its claim "
        "estimation time by a third."
    ),
    "Northgate Capital - portfolio notes": (
        "Northgate Capital is a venture firm that concentrates on climate "
        "and energy infrastructure. Partner Dana Okafor joined the board of "
        "Aster Systems after leading the 2021 investment round. The firm's "
        "largest holding is TerraCell, a geothermal utility operating in "
        "Iceland, which is also a Cirrus customer for storm forecasting."
    ),
}

SUGGESTED_QUESTIONS: tuple[str, ...] = (
    "Who founded Aster Systems and what product did it build?",
    "Which company sells the Cirrus weather platform?",
    "Who led the Cirrus rollout at Fernwood Insurance and what did it achieve?",
    "Which investors back Aster Systems, and what else do they hold?",
)
