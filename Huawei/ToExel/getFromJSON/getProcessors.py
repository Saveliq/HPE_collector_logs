from search import Resources


def get_processors(json_data):
    resources = Resources(json_data)
    return resources.installed(resources.children(resources.system_path, "Processors"), keep_absent=True)
