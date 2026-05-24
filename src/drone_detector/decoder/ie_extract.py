"""Walk the IE list of an 802.11 frame body, return (protocol_tag, payload) or None."""

DJI_OUI = b"\x60\x60\x1F"
DJI_DRONEID_V2_OUI_TYPE = 0x09
ASTM_OUI = b"\xfa\x0b\xbc"
ASTM_F3411_OUI_TYPE = 0x0D
VENDOR_SPECIFIC_ELEMENT_ID = 0xDD


def extract_drone_ie(frame_body: bytes) -> tuple[str, bytes] | None:
    """Walk the IE list; return (tag, payload) for the first recognized vendor IE."""
    i = 0
    n = len(frame_body)
    while i + 2 <= n:
        element_id = frame_body[i]
        length = frame_body[i + 1]
        start = i + 2
        end = start + length
        if end > n:
            return None  # truncated
        if element_id == VENDOR_SPECIFIC_ELEMENT_ID and length >= 4:
            oui = frame_body[start : start + 3]
            oui_type = frame_body[start + 3]
            inner = bytes(frame_body[start + 4 : end])
            if oui == DJI_OUI and oui_type == DJI_DRONEID_V2_OUI_TYPE:
                return ("dji_v2", inner)
            if oui == ASTM_OUI and oui_type == ASTM_F3411_OUI_TYPE:
                return ("astm_f3411", inner)
        i = end
    return None
