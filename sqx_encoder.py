"""
Прямой (компрессирующий) кодировщик формата sqx — обратная операция к sqx_codec.sqx_decode.

КЛЮЧЕВАЯ СЛОЖНОСТЬ: декодер читает управляющие 16-битные слова "лениво" — целиком,
в момент, когда требуется их ПЕРВЫЙ бит, а затем выдаёт из уже загруженного слова
биты по одному, перемежая это с прямым чтением байт данных (литералов/смещений/длин).
Поэтому позиция управляющего слова в выходном потоке определяется тем, КОГДА его
первый бит впервые понадобился, а не тем, когда мы (кодировщик) накопили все 16 бит
этого слова — а 16 бит слова могут "собираться" из битов нескольких разных операций.

Решение — два прохода:
  Pass 1: проходим по списку операций, для каждой генерируем нужные ей управляющие
          биты (выбор типа операции + при необходимости внутренние биты длины) и
          байты данных; копим единый плоский список всех управляющих бит и список
          "событий" (после какого количества бит из плоского списка должны быть
          выведены данные конкретной операции).
  Pass 2: плоский список бит режем на 16-битные слова (это и есть итоговые
          управляющие слова). Затем эмулируем порядок вывода: слово №g выводится
          в поток ровно перед данными первой операции, которой нужен хотя бы один
          бит из слова №g (так же, как декодер подгружает слово целиком при первом
          обращении к любому его биту).
"""
import struct


class SqxEncoder:
    def __init__(self, j1=0, j2=1, j3=2, c1=3):
        assert j1 + j2 + j3 == 3 and j1 != j2 and j2 != j3 and j3 != j1
        self.j1, self.j2, self.j3 = j1, j2, j3
        self.c1 = c1
        c2 = 0
        c3 = 0
        for _ in range(c1):
            c2 = ((c2 >> 1) | 0x80) & 0xFF
            c3 = ((c3 << 1) | 1) & 0xFF
        self.c2, self.c3 = c2, c3

        self._all_ctrl_bits = []     # плоский список всех управляющих бит, по порядку операций
        self._op_records = []        # [(end_bit_index, [data_bytes...]), ...]
        self._cur_bits = []          # биты текущей операции (накопитель перед коммитом)
        self._cur_data = []          # байты данных текущей операции

    # --- сбор бит/данных одной операции -----------------------------------------
    def _bit(self, b):
        self._cur_bits.append(b & 1)

    def _data_byte(self, value):
        assert 0 <= value <= 0xFF
        self._cur_data.append(("B", value))

    def _data_word(self, value):
        assert 0 <= value <= 0xFFFF
        self._cur_data.append(("W", value))

    def _commit_op(self):
        self._all_ctrl_bits.extend(self._cur_bits)
        end_idx = len(self._all_ctrl_bits)
        self._op_records.append((end_idx, self._cur_data))
        self._cur_bits = []
        self._cur_data = []

    def _select(self, op):
        if op == self.j1:
            self._bit(0)
        elif op == self.j2:
            self._bit(1); self._bit(0)
        else:
            self._bit(1); self._bit(1)

    # --- операции (вызывать в желаемом порядке) ----------------------------------
    def literal(self, byte_val):
        self._select(0)
        self._data_byte(byte_val)
        self._commit_op()

    def short_copy(self, offset, length):
        """offset: -1..-256, length: 2..5"""
        assert -256 <= offset <= -1
        L = length - 2
        assert 0 <= L <= 3
        self._select(1)
        self._bit((L >> 1) & 1)
        self._bit(L & 1)
        self._data_byte(offset + 256)
        self._commit_op()

    def long_copy(self, offset, length):
        """offset: отрицательный, length: 3.. (2+c3) напрямую, либо больше через escape."""
        assert offset < 0
        L = length - 2
        assert L >= 1
        self._select(2)
        off_unsigned = offset & 0xFFFF
        M = off_unsigned & ((1 << (16 - self.c1)) - 1)
        if L <= self.c3:
            word = ((M << self.c1) | L) & 0xFFFF
            self._data_word(word)
        else:
            assert 1 <= L <= 255
            word = (M << self.c1) & 0xFFFF  # низкие c1 бит = 0 -> length после маски = 0 -> escape
            self._data_word(word)
            self._data_byte(L)
        self._commit_op()

    def terminate(self):
        self._select(2)
        self._data_word(0)
        self._data_byte(0)
        self._commit_op()

    # --- финальная сборка (Pass 2) ------------------------------------------------
    def finish(self) -> bytes:
        self.terminate()

        bits = self._all_ctrl_bits
        pad = (-len(bits)) % 16
        bits = bits + [0] * pad
        n_words = len(bits) // 16
        words = []
        for g in range(n_words):
            w = 0
            for i in range(16):
                w |= (bits[g * 16 + i] << i)
            words.append(w)

        output = bytearray()
        flushed = 0  # сколько управляющих слов уже выведено в поток
        for end_idx, data_items in self._op_records:
            while flushed < n_words and flushed * 16 < end_idx:
                output += struct.pack('<H', words[flushed])
                flushed += 1
            for kind, value in data_items:
                if kind == "B":
                    output.append(value)
                else:
                    output += struct.pack('<H', value)
        while flushed < n_words:
            output += struct.pack('<H', words[flushed])
            flushed += 1
        return bytes(output)


def compress(data: bytes, j1=0, j2=1, j3=2, c1=3, min_match=3, max_window=None,
             allow_overlap=False, strategy="long_only", allow_escape=True) -> bytes:
    """Жадный LZ77.

    strategy:
      - "long_only" (по умолчанию, как раньше): все совпадения через long_copy.
      - "short_only": совпадения только через short_copy (offset -1..-256,
        длина 2..5) — длинные совпадения режутся на кусочки по 5 байт, более
        дальние совпадения вообще не используются (упадёт сжатие, но это
        диагностический режим: проверяем, работает ли short_copy там, где
        long_copy не работает).
      - "mixed": short_copy для offset<=256 (как делает оригинальный
        упаковщик игры — он использует short_copy очень активно), long_copy
        только для offset>256.

    allow_overlap=False по умолчанию: запрещает перекрывающиеся копии.

    allow_escape=True: если False, длинные совпадения длиннее (c3+2) байт
    режутся на части так, чтобы escape-байт long_copy вообще не использовался
    (диагностический режим — проверяем, не в нём ли дело).
    """
    enc = SqxEncoder(j1, j2, j3, c1)
    max_off = (1 << (16 - c1))
    if max_window:
        max_off = min(max_off, max_window)
    max_len = 257
    c3 = enc.c3
    max_direct_len = c3 + 2
    n = len(data)
    table = {}

    def find_best(i, cap_offset=None, cap_len=None):
        best_len = 0
        best_off = 0
        if i + 3 <= n:
            key = data[i:i + 3]
            cands = table.get(key)
            if cands:
                eff_max_off = max_off if cap_offset is None else min(max_off, cap_offset)
                lo = max(0, i - eff_max_off)
                lim_cap = max_len if cap_len is None else cap_len
                for p in reversed(cands):
                    if p < lo:
                        break
                    offset = i - p
                    limit = min(lim_cap, n - i)
                    if not allow_overlap:
                        limit = min(limit, offset)
                    L = 0
                    while L < limit and data[p + L] == data[i + L]:
                        L += 1
                    if L > best_len:
                        best_len = L
                        best_off = offset
                        if best_len >= lim_cap:
                            break
        return best_off, best_len

    def add_pos(i):
        if i + 3 <= n:
            table.setdefault(data[i:i + 3], []).append(i)

    i = 0
    while i < n:
        if strategy == "short_only":
            best_off, best_len = find_best(i, cap_offset=256)
            best_len = min(best_len, 5)
        else:
            cap_len = max_direct_len if not allow_escape else None
            best_off, best_len = find_best(i, cap_len=cap_len)

        if best_len >= min_match:
            if strategy == "short_only":
                enc.short_copy(-best_off, best_len)
            elif strategy == "mixed" and best_off <= 256:
                remaining = best_len
                while remaining >= min_match:
                    chunk = min(remaining, 5)
                    if chunk < 2:
                        break
                    enc.short_copy(-best_off, chunk)
                    remaining -= chunk
                best_len -= remaining
            else:
                enc.long_copy(-best_off, best_len)
            end = i + best_len
            while i < end:
                add_pos(i)
                i += 1
        else:
            add_pos(i)
            enc.literal(data[i])
            i += 1
    return enc.finish()
