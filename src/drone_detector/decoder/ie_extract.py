"""Extract the DJI DroneID v2 vendor-specific IE payload from an 802.11 frame body."""

DJI_OUI = b"\x60\x60\x1F"
DJI_DRONEID_V2_OUI_TYPE = 0x09
VENDOR_SPECIFIC_ELEMENT_ID = 0xDD


def extract_dji_ie(frame_body: bytes) -> bytes | None:
    """Walk the IE list in `frame_body`; return the DJI DroneID payload or None."""
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
            if oui == DJI_OUI and oui_type == DJI_DRONEID_V2_OUI_TYPE:
                return bytes(frame_body[start + 4 : end])
        i = end
    return None
