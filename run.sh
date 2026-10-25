#!/bin/sh
# Сгенерировано Claude
# Запуск программы. Первый аргумент - номер задачи, остальные передаются как есть.
# Примеры:
#   ./run.sh 1.1 --seed 1 tests/variant_basic.json 20
#   ./run.sh 1.2 --mode 2 tests/memoryless.json 2 0.001 5
#   ./run.sh 1.3 compress tests/archiver/text_en.txt --stats
#   ./run.sh --variant
dir="$(dirname "$0")"
case "$1" in
    1.1) shift; exec python3 "$dir/source_extended.py" "$@" ;;
    1.2) shift; exec python3 "$dir/uniform_coding.py" "$@" ;;
    1.3) shift; exec python3 "$dir/archiver.py" "$@" ;;
    --variant) exec python3 "$dir/source_extended.py" --variant ;;
    *)
        echo "Использование: ./run.sh 1.1|1.2|1.3 аргументы ... или ./run.sh --variant"
        exit 1
        ;;
esac

# Конец блока
