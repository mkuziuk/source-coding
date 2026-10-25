import argparse
import json
import sys
from fractions import Fraction
from math import factorial, floor, lcm, log2

from source_extended import Source, variant_text


def entropy(probabilities):
    H = 0
    for p in probabilities:
        if p == 0:
            continue
        H -= p * log2(p)

    return H


def memoryless_distribution(source):
    # распределение символа, если источник стационарный и без памяти, иначе ValueError
    if source.kind == "markov":
        raise ValueError(f"у источника есть память (memory = {source.memory})")

    if source.kind == "mixture":
        distributions = [memoryless_distribution(c) for c in source.components.values()]
        if any(d != distributions[0] for d in distributions):
            raise ValueError("смесь разных источников: такты зависимы, то есть есть память")
        return distributions[0]

    # распределение символа на каждой позиции source
    symbols = sorted({symbol for model in source.models.values() for symbol in model})
    distributions = []
    for name in source.source:
        switch = source.switches[name]
        distribution = {}
        for symbol in symbols:
            p = sum(w * source.models[model].get(symbol, 0) for model, w in switch.items())
            if p != 0:
                distribution[symbol] = p
        distributions.append(distribution)

    for j, distribution in enumerate(distributions):
        if distribution != distributions[0]:
            raise ValueError(f"источник не стационарный: на позиции {j} source "
                             f"распределение символа другое, чем на позиции 0")
    return distributions[0]


def all_counts(n, k):
    # все наборы счётчиков [c_1, ..., c_k] с суммой n, то есть все типы блоков
    if k == 1:
        return [[n]]
    result = []
    for c in range(n + 1):
        for rest in all_counts(n - c, k - 1):
            result.append([c] + rest)
    return result


# The latest fast version is written by Claude
def p_e(probs, n, l, q):
    # p_j = a_j / D, тогда вероятность блока = a_1^c_1 * ... * a_k^c_k / D^n.
    # Знаменатель D^n у всех блоков общий, поэтому сортируем и складываем
    # только целые числители. Это точно и намного быстрее, чем Fraction.
    # слов хватает на все блоки. Проверка l >= n * k нужна, чтобы при огромном l
    # не считать q^l: q^l >= 2^l >= 2^(n * k) >= k^n
    k = len(probs)
    if l >= n * k or q ** l >= k ** n:
        return Fraction(0), None

    D = lcm(*(p.denominator for p in probs))
    a = [int(p * D) for p in probs]
    powers = [[x ** c for c in range(n + 1)] for x in a]
    fact = [factorial(c) for c in range(n + 1)]

    types = []
    for counts in all_counts(n, k):
        weight = 1  # числитель вероятности одного блока этого типа
        num = fact[n]  # число блоков этого типа
        for j, c in enumerate(counts):
            weight *= powers[j][c]
            num //= fact[c]
        types.append((weight, num, counts))

    # сначала самые вероятные блоки
    types.sort(reverse=True)

    # набираем q^l блоков, у последнего типа можно взять часть
    remaining = q ** l
    covered = 0
    chosen = []  # (счётчики типа, сколько блоков взято, сколько всего)
    for weight, num, counts in types:
        take = min(num, remaining)
        covered += take * weight
        remaining -= take
        chosen.append((counts, take, num))
        if remaining == 0:
            break

    return 1 - Fraction(covered, D ** n), chosen

# end


def write_code(file_name, symbols, n, l, q, chosen):
    with open(file_name, "w", encoding="utf-8") as file:
        # written by Claude
        file.write(f"n = {n}\n")
        file.write(f"l = {l}\n")
        file.write(f"q = {q}\n")
        file.write("alphabet = " + " ".join(symbols) + "\n")
        file.write("# Кодируются q^l наиболее вероятных блоков длины n.\n")
        file.write("# Блоки идут по типам в порядке строк ниже, внутри типа - в лексикографическом порядке.\n")
        file.write("# Если у типа взяты не все блоки, берутся первые по этому порядку.\n")
        file.write("# Кодовое слово блока - его номер (с 0) в этом порядке, записанный по основанию q, длина l.\n")
        file.write("# Блок, которого нет в списке, закодировать нельзя: это ошибка декодирования.\n")
        # end
        if chosen is None:
            file.write("# q^l >= k^n, поэтому кодируются все блоки длины n.\n")
            return
        file.write("# тип (сколько раз каждый символ) : взято блоков из всего блоков типа\n")
        for counts, take, num in chosen:
            type_text = " ".join(f"{symbol}={c}" for symbol, c in zip(symbols, counts))
            file.write(f"{type_text} : {take} из {num}\n")


def mode_1(source):
    try:
        distribution = memoryless_distribution(source)
    except ValueError as error:
        print(f"Условие не выполнено: {error}")
        return

    print("Источник стационарный и без памяти")
    for symbol, p in distribution.items():
        print(f"P({symbol}) = {p}")
    print(f"H(X) = {entropy(distribution.values()):.6f} бит")


def mode_2(distribution, R, eps, q, nmax, code_file):
    symbols = list(distribution)
    probs = list(distribution.values())
    H = entropy(probs)

    print(f"H(X) = {H:.6f} бит, R = {R} ~ {float(R):.6g} бит, eps = {float(eps):g}, q = {q}")
    print()
    print("n", "l", "P_e(n)")
    min_n = None
    for n in range(1, nmax + 1):
        l = floor(n * R / log2(q))
        error, chosen = p_e(probs, n, l, q)
        print(n, l, float(error))
        if min_n is None and error <= eps:
            min_n, min_l, min_chosen = n, l, chosen

    print()
    if min_n is None:
        print(f"P_e(n) <= eps не выполняется ни при одном n от 1 до {nmax}")
    else:
        print(f"Минимальное n, при котором P_e(n) <= eps: n = {min_n}, l = {min_l}")
        write_code(code_file, symbols, min_n, min_l, q, min_chosen)
        print(f"Описание кода записано в {code_file}")

    print()
    if R > H:
        print("n0 существует: R > H(X), поэтому P_e(n) -> 0 и с некоторого n0 P_e(n) <= eps")
    elif R < H:
        print("n0 не существует: R < H(X), поэтому P_e(n) -> 1 и при больших n P_e(n) > eps")
        print("При малых n условие P_e(n) <= eps может выполняться в любом случае")
    else:
        print("R = H(X): граничный случай")


def parse_number(name, text):
    try:
        return Fraction(text)
    except (ValueError, ZeroDivisionError):
        raise ValueError(f"{name}: некорректное число '{text}'")


def main():
    # Written by Claude
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("params", nargs="*", help="R eps q для режима 2")
    parser.add_argument("--mode", type=int, choices=[1, 2], default=1)
    parser.add_argument("--nmax", type=int, default=50)
    parser.add_argument("--code", default="code.txt", help="файл для описания кода")
    parser.add_argument("--variant", action="version", version=variant_text())
    args = parser.parse_args()

    try:
        with open(args.source, encoding="utf-8") as file:
            source = Source(json.load(file))

        if args.mode == 2:
            if len(args.params) != 3:
                raise ValueError("в режиме 2 нужны три параметра: R eps q")
            R = parse_number("R", args.params[0])
            eps = parse_number("eps", args.params[1])
            q = parse_number("q", args.params[2])
            if q.denominator != 1:
                raise ValueError("q должно быть целым")
            q = int(q)
            if R <= 0:
                raise ValueError("R должно быть больше 0")
            if not 0 < eps < 1:
                raise ValueError("eps должно быть между 0 и 1")
            if q < 2:
                raise ValueError("q должно быть не меньше 2")
            if args.nmax < 1:
                raise ValueError("nmax должно быть не меньше 1")
            distribution = memoryless_distribution(source)
    except (OSError, ValueError) as error:
        print(f"Ошибка: {error}")
        sys.exit(1)

    # end

    try:
        if args.mode == 1:
            mode_1(source)
        else:
            mode_2(distribution, R, eps, q, args.nmax, args.code)
    except (OSError, OverflowError) as error:
        print(f"Ошибка: {error}")
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        print("Прервано пользователем")
        sys.exit(1)


if __name__ == "__main__":
    main()
