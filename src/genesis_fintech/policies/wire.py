"""Versioned, bounded JSON-line protocol shared by supervisor and worker.

No generator/evaluator imports. All protocol errors are intentionally generic.
"""

import json

PROTOCOL_VERSION = 1
MAX_FRAME_BYTES = 512 * 1024


class ProtocolError(ValueError):
    pass


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ProtocolError("invalid worker frame")
        result[key] = value
    return result


def _constant(value):
    raise ProtocolError("invalid worker frame")


def encode_frame(request_id, field, value):
    try:
        data = json.dumps({"protocol_version": PROTOCOL_VERSION, "request_id": request_id, field: value},
                          allow_nan=False, separators=(",", ":"), ensure_ascii=True).encode() + b"\n"
    except (ValueError, TypeError, RecursionError) as exc:
        raise ProtocolError("invalid worker frame") from exc
    if len(data) > MAX_FRAME_BYTES:
        raise ProtocolError("invalid worker frame")
    return data


def decode_frame(data, request_id, field):
    if len(data) > MAX_FRAME_BYTES or not data.endswith(b"\n") or b"\n" in data[:-1]:
        raise ProtocolError("invalid worker frame")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ProtocolError("invalid worker frame") from exc
    if (type(value) is not dict or set(value) != {"protocol_version", "request_id", field}
            or type(value["protocol_version"]) is not int or value["protocol_version"] != PROTOCOL_VERSION
            or type(value["request_id"]) is not int or value["request_id"] != request_id):
        raise ProtocolError("invalid worker frame")
    return value[field]
