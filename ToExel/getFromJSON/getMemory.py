import re

from search import search_one, stripJSON


def get_memory(json_data):
    def _get(data, id_node):
        node_result = {}
        node_result["DIMMStatus"] = search_one(data, r"DIMMStatus")
        node_result["Technology"] = search_one(data,  value_pattern=r".*DDR.*")
        node_result["Manufacturer"] = search_one(data, r"Manufacturer")
        node_result["Frequency"] = search_one(data, r"MaximumFrequencyMHz") if search_one(data, r"MaximumFrequencyMHz") else search_one(data, r"MaxOperatingSpeedMTs")
        node_result["Name"] = search_one(data, r"Name")
        node_result["PartNumber"] = search_one(data, r"PartNumber", value_pattern=r".*-.{3}", value_type=str)
        node_result["Model"] = search_one(data, r"PartNumber", value_pattern=r".{13,}", value_type=str)
        node_result["VendorName"] = search_one(data, r"VendorName")
        node_result["Rank"] = search_one(data, r"Rank")
        node_result["SizeMB"] =  search_one(data, r"CapacityMiB") if search_one(data, r"CapacityMiB") else search_one(data, r"SizeMB")
        return node_result

    def match_by_pattern(data, pattern, descr="UNDEF", func=None):
        result = []
        pattern = re.compile(pattern)
        nodes = {
            key: val for key, val in data.items() if pattern.match(key)
        }
        ind = 0
        for key, _data in nodes.items():
            result.append(func(_data, int(key[-1])))
            ind += 1
        return result

    return stripJSON(match_by_pattern(json_data, r".*/Memory/proc\d+(-\d+)?dimm\d+(-\d+)?", "Memory_", func=_get))

