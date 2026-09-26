import re

from search import SYSTEM, Resources, _installed, stripJSON


def get_processors(json_data):
    resources = Resources(json_data)
    # Keep explicit empty sockets for the writer's existing summary-fallback guard.
    return stripJSON(_installed(
        resources, resources.matching(re.escape(SYSTEM) + r"/Processors/[^/]+"), keep_absent=True))
