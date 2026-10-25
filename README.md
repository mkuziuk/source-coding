# ДЗ 1. Кодирование источников

Все команды запускаются из этой папки.

```
./run.sh --variant
```

## Задача 1.1. Моделирование источника

```
./run.sh 1.1 [--seed S] файл.json N                     # режим 1: реализация длины N
./run.sh 1.1 [--seed S] файл.json None                  # режим 1: бесконечно, остановка Ctrl+C
./run.sh 1.1 --mode 2 [--seed S] файл.json N a1 ... ar  # режим 2: вероятности и частотная оценка
```

Примеры:

```
./run.sh 1.1 --seed 1 tests/variant_basic.json 20
./run.sh 1.1 --mode 2 --seed 10 tests/variant_basic.json 1000 a b
```

## Задача 1.2. Равномерное кодирование

```
./run.sh 1.2 файл.json                                            # режим 1: проверка и энтропия
./run.sh 1.2 --mode 2 [--nmax 50] [--code code.txt] файл.json R eps q  # режим 2: таблица P_e(n)
```

Описание кода записывается в `code.txt` в текущей папке (имя меняется через `--code`).

Примеры:

```
./run.sh 1.2 tests/memoryless.json
./run.sh 1.2 --mode 2 tests/memoryless.json 2 0.001 5
```

## Задача 1.3. Архиватор ZipMeHuffman

```
./run.sh 1.3 compress файл [--stats]   # результат: файл.zmh
./run.sh 1.3 decompress файл.zmh       # результат: файл без .zmh
```

Существующий файл при восстановлении не перезаписывается.

Примеры:

```
./run.sh 1.3 compress tests/archiver/text_en.txt --stats
mkdir /tmp/restore && cp tests/archiver/text_en.txt.zmh /tmp/restore/
./run.sh 1.3 decompress /tmp/restore/text_en.txt.zmh
```

## Файлы

- `REPORT.md` - отчёт;
- `FORMAT.md` - спецификация расширенного формата;
- `RESULTS.md` - вывод программ на тестах;
- `SOURCES.md` - внешние источники;
- `tests/` - тесты.
