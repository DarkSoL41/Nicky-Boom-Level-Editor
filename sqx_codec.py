"""
sqx_codec.py — декодер формата сжатия "sqx", используемого во всех ресурсах
игры Nicky Boom (Microids, 1992): DECORx.CDG, DECORx.BLK, DECORx.REF,
POSITx.REF, REFx.REF.

Это прямой порт функции sqx_decode() из sqx_decoder.c — исходников движка
"Nicky" (переписанная реализация игры), автор Gregory Montoir (cyx),
http://cyxdown.free.fr/nicky/  (release nicky-0.2.0-src.zip).

Алгоритм — байт-ориентированный LZ-кодер с тремя типами операций
(литерал / короткий повтор со смещением -1..-256 / длинный повтор с
произвольным смещением), порядок которых для конкретного файла задаётся
переставленной троицей (j1, j2, j3) из первых байтов потока. Управляющие
биты читаются из 16-битных слов (little-endian), подгружаемых по необходимости.

Формат файла на диске:
    байты 0-1   : пропускаются (служебные/контрольные, не часть потока sqx)
    байт   2    : j1   (значения j1,j2,j3 — перестановка {0,1,2}, см. ниже)
    байт   3    : j2
    байт   4    : j3
    байт   5    : c1   (параметр сдвига для длинных смещений)
    байты 6..   : сжатый поток

Итого «шапка» = 6 байт.
"""

from __future__ import annotations


def _read_u16le(buf: bytes, i: int) -> int:
    return buf[i] | (buf[i + 1] << 8)


class _SqxDecoder:
    __slots__ = ("src", "sp", "dst", "code", "carry")

    def __init__(self, src: bytes):
        self.src = src
        self.sp = 0
        self.dst = bytearray()
        self.code = 1
        self.carry = 0

    # --- байтовый/словный ввод -------------------------------------------------
    def _byte(self) -> int:
        b = self.src[self.sp]
        self.sp += 1
        return b

    def _word(self) -> int:
        v = _read_u16le(self.src, self.sp)
        self.sp += 2
        return v

    # --- битовые операции над 16-битным регистром "code" -----------------------
    def _shr(self) -> None:
        self.carry = self.code & 1
        self.code = (self.code >> 1) & 0xFFFF

    def _rcr(self) -> None:
        c = self.code & 1
        self.code = (self.code >> 1) & 0xFFFF
        if self.carry:
            self.code |= 0x8000
        self.carry = c

    def _rcl_into(self, box: list[int]) -> None:
        """rcl для произвольного 16-битного аккумулятора (используется для len)."""
        c = (box[0] & 0x8000) != 0
        box[0] = (box[0] << 1) & 0xFFFF
        if self.carry:
            box[0] |= 1
        self.carry = c

    # --- три типа операций (helper1/2/3 из оригинала) ---------------------------
    def _op_literal(self) -> int:
        """Тип 0: один литеральный байт."""
        self.dst.append(self._byte())
        return 0

    def _op_short_copy(self) -> int:
        """Тип 1: повтор с однобайтовым смещением (-1..-256), длина 2..5."""
        length = [0]
        self._shr()
        if self.code == 0:
            self.code = self._word()
            self._rcr()
            self._rcl_into(length)
            self._shr()
        else:
            self._rcl_into(length)
            self._shr()
            if self.code == 0:
                self.code = self._word()
                self._rcr()
        self._rcl_into(length)

        offset = 0xFF00 | self._byte()
        off16 = offset - 0x10000 if offset >= 0x8000 else offset
        src_pos = len(self.dst) + off16
        for i in range(length[0] + 2):
            self.dst.append(self.dst[src_pos + i])
        return 0

    def _op_long_copy(self, c1: int, c2: int, c3: int) -> int:
        """Тип 2: повтор с двухбайтовым смещением произвольной длины.
        Возвращает 1, если встречен маркер конца потока."""
        word = self._word()
        length = word & 0xFF
        offset = (word >> c1) & 0xFFFF
        offset |= c2 << 8
        length &= c3
        if length == 0:
            length = self._byte()
            if length == 0:
                return 1  # конец потока
        off16 = offset - 0x10000 if offset >= 0x8000 else offset
        src_pos = len(self.dst) + off16
        for i in range(length + 2):
            self.dst.append(self.dst[src_pos + i])
        return 0

    def decode(self) -> bytes:
        j1, j2, j3 = self._byte(), self._byte(), self._byte()
        assert j1 + j2 + j3 == 3 and j1 != j2 and j2 != j3 and j3 != j1, (j1, j2, j3)
        c1 = self._byte()
        c2 = 0
        c3 = 0
        for _ in range(c1):
            c2 = ((c2 >> 1) | 0x80) & 0xFF
            c3 = ((c3 << 1) | 1) & 0xFF

        ops = [self._op_literal, self._op_short_copy, lambda: self._op_long_copy(c1, c2, c3)]
        order = [j1, j2, j3]

        end = 0
        while not end:
            self._shr()
            if self.code == 0:
                self.code = self._word()
                self._rcr()
            if not self.carry:
                end = ops[order[0]]()
                continue
            self._shr()
            if self.code == 0:
                self.code = self._word()
                self._rcr()
            if not self.carry:
                end = ops[order[1]]()
            else:
                end = ops[order[2]]()
        return bytes(self.dst)


def sqx_decode(raw: bytes, skip: int = 2) -> bytes:
    """Распаковать файл ресурса Nicky Boom (.CDG/.BLK/.REF/...).

    `raw`  — полное содержимое файла, как он лежит на диске.
    `skip` — сколько байт пропустить перед разбором заголовка sqx
             (в оригинальном движке вызывается как sqx_decode(data + 2, dst),
             поэтому по умолчанию 2).
    """
    return _SqxDecoder(raw[skip:]).decode()


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("usage: python3 sqx_codec.py <input> <output>")
        sys.exit(1)
    data = open(sys.argv[1], "rb").read()
    out = sqx_decode(data)
    open(sys.argv[2], "wb").write(out)
    print(f"decoded {len(data)} -> {len(out)} bytes")
