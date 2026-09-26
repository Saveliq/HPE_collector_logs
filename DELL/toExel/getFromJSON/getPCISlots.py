from search import CHASSIS, Resources, _dict, _list, stripJSON


def get_PCI_slots(json_data):
    resources = Resources(json_data)
    slots = resources.data.get(CHASSIS + "/PCIeSlots", {})
    result = {}
    for index, slot in enumerate(_list(slots.get("Slots")), 1):
        if not isinstance(slot, dict):
            continue
        result["NetworkAdapter_" + str(index)] = {
            "Name": slot.get("Name") or slot.get("SlotType"),
            "Status": _dict(slot.get("Status")).get("State"),
        }
    return stripJSON(result)
