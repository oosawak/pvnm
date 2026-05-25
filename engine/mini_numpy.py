"""Tiny NumPy fallback for PVNM Web runtime cache loading.

This is not a general NumPy replacement. It only supports the small subset PVNM
needs at runtime when original images are absent and prebuilt ``.npy`` cache
files are available.
"""
from __future__ import annotations

import ast
import io
import struct
from typing import Iterable


uint8 = "uint8"


class MiniRow:
    def __init__(self, owner: "MiniArray", row: int) -> None:
        self._owner = owner
        self._row = row

    def __getitem__(self, col: int) -> int:
        return self._owner[self._row, col]

    def __iter__(self):
        cols = self._owner.shape[1] if len(self._owner.shape) > 1 else 1
        for col in range(cols):
            yield self[col]

    def __len__(self) -> int:
        return self._owner.shape[1] if len(self._owner.shape) > 1 else 1


class MiniArray:
    def __init__(self, shape: tuple[int, ...], data: bytes | bytearray | None = None) -> None:
        self.shape = tuple(int(v) for v in shape)
        total = 1
        for value in self.shape:
            total *= max(0, int(value))
        self._data = bytearray(data or b"\x00" * total)
        if len(self._data) < total:
            self._data.extend(b"\x00" * (total - len(self._data)))
        elif len(self._data) > total:
            del self._data[total:]

    def __len__(self) -> int:
        return self.shape[0] if self.shape else 0

    def copy(self) -> "MiniArray":
        return MiniArray(self.shape, self._data)

    def __getitem__(self, key):
        if isinstance(key, tuple):
            return self._data[self._offset(key)]
        if isinstance(key, slice):
            rng = range(*key.indices(len(self)))
            if len(self.shape) <= 1:
                return [self._data[i] for i in rng]
            return [tuple(MiniRow(self, i)) for i in rng]
        if len(self.shape) <= 1:
            idx = int(key)
            if idx < 0:
                idx += len(self)
            if idx < 0 or idx >= len(self):
                raise IndexError("MiniArray index out of range")
            return self._data[idx]
        row = int(key)
        if row < 0:
            row += len(self)
        if row < 0 or row >= len(self):
            raise IndexError("MiniArray index out of range")
        return MiniRow(self, row)

    def __setitem__(self, key, value) -> None:
        if isinstance(key, tuple):
            self._data[self._offset(key)] = int(value) & 0xFF
            return
        row = int(key)
        if len(self.shape) <= 1:
            self._data[row] = int(value) & 0xFF
            return
        cols = self.shape[1]
        if isinstance(value, MiniRow):
            value = list(value)
        if not isinstance(value, (list, tuple)):
            value = [value] * cols
        base = row * cols
        for col in range(cols):
            item = value[col] if col < len(value) else 0
            self._data[base + col] = int(item) & 0xFF

    def _offset(self, key: tuple[int, ...]) -> int:
        if len(self.shape) == 1:
            return int(key[0])
        row, col = int(key[0]), int(key[1])
        return row * self.shape[1] + col

    def tobytes(self) -> bytes:
        return bytes(self._data)


ndarray = MiniArray


def zeros(shape, dtype=None) -> MiniArray:
    if isinstance(shape, int):
        shape = (shape,)
    return MiniArray(tuple(shape))


def asarray(value, dtype=None) -> MiniArray:
    if isinstance(value, MiniArray):
        return value
    if hasattr(value, "shape") and hasattr(value, "tobytes"):
        try:
            return MiniArray(tuple(value.shape), value.tobytes())
        except Exception:
            pass
    rows = list(value or [])
    if not rows:
        return MiniArray((0,))
    if isinstance(rows[0], (list, tuple, MiniRow)):
        cols = len(rows[0])
        flat = bytearray()
        for row in rows:
            items = list(row)
            for col in range(cols):
                flat.append(int(items[col] if col < len(items) else 0) & 0xFF)
        return MiniArray((len(rows), cols), flat)
    return MiniArray((len(rows),), bytearray(int(v) & 0xFF for v in rows))


def array(value, dtype=None) -> MiniArray:
    return asarray(value, dtype=dtype)


def ascontiguousarray(value) -> MiniArray:
    return asarray(value)


def load(path) -> MiniArray:
    close = False
    if isinstance(path, (bytes, bytearray, memoryview)):
        f = io.BytesIO(bytes(path))
    elif hasattr(path, "read"):
        f = path
    else:
        f = open(path, "rb")
        close = True
    try:
        magic = f.read(6)
        if magic != b"\x93NUMPY":
            raise ValueError("not a numpy file")
        major = f.read(1)[0]
        _minor = f.read(1)[0]
        if major == 1:
            header_len = struct.unpack("<H", f.read(2))[0]
        elif major in (2, 3):
            header_len = struct.unpack("<I", f.read(4))[0]
        else:
            raise ValueError(f"unsupported npy version {major}")
        header = f.read(header_len).decode("latin1").strip()
        meta = ast.literal_eval(header)
        descr = str(meta.get("descr", ""))
        if descr not in ("|u1", "uint8"):
            raise ValueError(f"unsupported dtype {descr}")
        if bool(meta.get("fortran_order")):
            raise ValueError("fortran-order arrays are not supported")
        shape = tuple(int(v) for v in meta.get("shape", ()))
        return MiniArray(shape, f.read())
    finally:
        if close:
            f.close()


def load_bytes(data: bytes) -> MiniArray:
    return load(data)


def save(path: str, arr) -> None:
    data = asarray(arr)
    shape = data.shape
    header = {
        "descr": "|u1",
        "fortran_order": False,
        "shape": shape,
    }
    header_text = repr(header)
    header_bytes = header_text.encode("latin1")
    pad = 16 - ((10 + len(header_bytes) + 1) % 16)
    header_bytes += b" " * pad + b"\n"
    with open(path, "wb") as f:
        f.write(b"\x93NUMPY")
        f.write(bytes([1, 0]))
        f.write(struct.pack("<H", len(header_bytes)))
        f.write(header_bytes)
        f.write(data.tobytes())
