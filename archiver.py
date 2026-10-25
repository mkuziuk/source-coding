import argparse
import heapq
import struct
import sys
from math import log2

from source_extended import variant_text

MAGIC = b"ZMH1"
# размер исходного (8), CRC исходного (4), длина данных (8), число символов (2)
FIELDS = ">QIQH"
FIELDS_SIZE = struct.calcsize(FIELDS)

# Сделать crc32 предложил Claude и помог реализовать

def make_crc_table():
    table = []
    for i in range(256):
        c = i
        for _ in range(8):
            if c % 2 == 1:
                c = (c // 2) ^ 0xEDB88320
            else:
                c //= 2
        table.append(c)
    return table


CRC_TABLE = make_crc_table()


def crc32(data):
    crc = 0xFFFFFFFF
    for byte in data:
        crc = CRC_TABLE[(crc ^ byte) % 256] ^ (crc // 256)
    return crc ^ 0xFFFFFFFF

# end

def count_bytes(data):
    freq = {}
    for byte in data:
        freq[byte] = freq.get(byte, 0) + 1
    return freq


def code_lengths(freq):
    # длины кодов Хаффмана: при каждом слиянии двух узлов
    # длина кода всех символов в них растёт на 1
    if len(freq) == 1:
        return {byte: 1 for byte in freq}

    lengths = {byte: 0 for byte in freq}
    # второе поле - номер узла, чтобы при равных частотах не сравнивать списки
    heap = [(count, i, [byte]) for i, (byte, count) in enumerate(freq.items())]
    heapq.heapify(heap)
    i = len(heap)
    while len(heap) > 1:
        count1, _, bytes1 = heapq.heappop(heap)
        count2, _, bytes2 = heapq.heappop(heap)
        for byte in bytes1 + bytes2:
            lengths[byte] += 1
        heapq.heappush(heap, (count1 + count2, i, bytes1 + bytes2))
        i += 1
    return lengths


def canonical_codes(lengths):
    # канонический код: по длинам кодов коды восстанавливаются однозначно,
    # поэтому в файле хранятся только длины
    codes = {}
    code = 0
    previous_length = 0
    for byte in sorted(lengths, key=lambda b: (lengths[b], b)):
        code *= 2 ** (lengths[byte] - previous_length)
        codes[byte] = format(code, f"0{lengths[byte]}b")
        code += 1
        previous_length = lengths[byte]
    return codes


def compress(data):
    # первый проход: модель
    freq = count_bytes(data)
    lengths = code_lengths(freq)
    codes = canonical_codes(lengths)

    # второй проход: кодирование, последний байт дополняется нулями
    bits = "".join(codes[byte] for byte in data)
    bits += "0" * (-len(bits) % 8)
    packed = int(bits, 2).to_bytes(len(bits) // 8, "big") if bits else b""

    header = MAGIC + struct.pack(FIELDS, len(data), crc32(data), len(packed), len(lengths))
    for byte in sorted(lengths):
        header += bytes([byte, lengths[byte]])
    header += struct.pack(">I", crc32(header))

    return header, packed, freq, lengths

# Обработку ошибок помог сделать Claude
def decompress(raw):
    # файл короче 4 байт, но совпадающий с началом сигнатуры, считается обрезанным
    if not MAGIC.startswith(raw[:4]):
        raise ValueError("чужой формат: нет сигнатуры ZMH1")
    if len(raw) < len(MAGIC) + FIELDS_SIZE:
        raise ValueError("файл обрезан: неполный заголовок")

    # поля фиксированной длины сразу после сигнатуры
    size, data_crc, packed_size, count = struct.unpack_from(FIELDS, raw, len(MAGIC))
    if count > 256:
        raise ValueError("файл повреждён: в заголовке больше 256 символов")
    # сигнатура + поля + пары (байт, длина) + CRC заголовка
    header_size = len(MAGIC) + FIELDS_SIZE + 2 * count + 4
    if len(raw) < header_size:
        raise ValueError("файл обрезан: неполный заголовок")

    # CRC заголовка записан в его последних 4 байтах
    (header_crc,) = struct.unpack_from(">I", raw, header_size - 4)
    if crc32(raw[:header_size - 4]) != header_crc:
        raise ValueError("файл повреждён: не сходится контрольная сумма заголовка")

    # заголовок цел, значит packed_size верный и по нему видно, обрезаны ли данные
    packed = raw[header_size:]
    if len(packed) < packed_size:
        raise ValueError(f"файл обрезан: данных {len(packed)} байт из {packed_size}")
    if len(packed) > packed_size:
        raise ValueError("файл повреждён: лишние байты после данных")

    # по длинам строим те же канонические коды, что и при сжатии
    lengths = {}
    for j in range(count):
        position = len(MAGIC) + FIELDS_SIZE + 2 * j
        lengths[raw[position]] = raw[position + 1]
    decode = {code: byte for byte, code in canonical_codes(lengths).items()}

    # читаем биты по одному, пока накопленная строка не совпадёт с кодом.
    # Код префиксный, поэтому первое совпадение и есть нужный символ.
    # Останавливаемся после size символов: дальше идут нули дополнения
    bits = "".join(format(byte, "08b") for byte in packed)
    result = bytearray()
    current = ""
    for bit in bits:
        if len(result) == size:
            break
        current += bit
        if current in decode:
            result.append(decode[current])
            current = ""

    # если данные повреждены, символов может не хватить или они будут другими
    if len(result) != size or crc32(result) != data_crc:
        raise ValueError("файл повреждён: не сходится контрольная сумма данных")
    return bytes(result)

# end


def entropy(freq, total):
    H = 0
    for count in freq.values():
        H -= count / total * log2(count / total)
    return H


def print_stats(data, header, packed, freq, lengths):
    total = len(data)
    print(f"Исходный размер: {total} байт")
    if total > 0:
        print(f"Энтропия H: {entropy(freq, total):.4f} бит на байт")
        average = sum(freq[byte] * lengths[byte] for byte in freq) / total
        print(f"Средняя длина кода: {average:.4f} бит на байт")
    print(f"Заголовок: {len(header)} байт")
    print(f"Данные: {len(packed)} байт")
    print(f"Сжатый размер: {len(header) + len(packed)} байт")
    if total > 0:
        print(f"Коэффициент сжатия: {total / (len(header) + len(packed)):.4f}")


def main():
    # written by claude
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["compress", "decompress"])
    parser.add_argument("file")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--variant", action="version", version=variant_text())
    args = parser.parse_args()
    # end

    try:
        with open(args.file, "rb") as file:
            raw = file.read()

        if args.command == "compress":
            header, packed, freq, lengths = compress(raw)
            output = args.file + ".zmh"
            with open(output, "wb") as file:
                file.write(header + packed)
            print(f"Сжато в {output}")
            if args.stats:
                print_stats(raw, header, packed, freq, lengths)
        else:
            if not args.file.endswith(".zmh"):
                raise ValueError("ожидается файл с расширением .zmh")
            data = decompress(raw)
            output = args.file[:-len(".zmh")]
            with open(output, "xb") as file:
                file.write(data)
            print(f"Восстановлено в {output}: {len(data)} байт, контрольная сумма совпала")
    except (OSError, ValueError) as error:
        print(f"Ошибка: {error}")
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        print("Прервано пользователем")
        sys.exit(1)


if __name__ == "__main__":
    main()
