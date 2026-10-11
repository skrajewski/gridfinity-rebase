# Pomiar wydajności

Wykonano 11 października 2026, macOS 26.2 arm64, Python 3.11.14,
Manifold 3.5.4, NumPy 2.4.6. Każdy scenariusz uruchomiono 5 razy.

Komenda: `uv run python scripts/benchmark.py --runs 5 --json`.
Proces CLI uruchamiany jest jako osobny proces Pythona; pomiar obejmuje
start, importy, odczyt, walidację, podmianę i zapis STL. Kolumna silnika
obejmuje odczyt, walidację, podmianę i zapis po załadowaniu bibliotek,
z pamięcią podręczną pojedynczej stopki. Pliki pozostają w cache systemu.

| Scenariusz | Trójkąty wejścia | Cały proces, mediana | Silnik po rozgrzaniu, mediana |
| --- | ---: | ---: | ---: |
| example/plain | 4500 | 91.16 ms | 18.17 ms |
| example/rebuilt | 4500 | 92.59 ms | 19.74 ms |
| example/rebuilt-screws | 4500 | 100.99 ms | 23.87 ms |
| example/refined | 4500 | 89.26 ms | 19.67 ms |
| example/press-fit | 4500 | 88.32 ms | 19.25 ms |
| example/donor | 4500 | 90.39 ms | 24.9 ms |
| 6x6/refined | 58246 | 288.12 ms | 206.84 ms |

`example` to rzeczywisty `tmp/test.stl`; `6x6` to wygenerowany pojemnik
z bocznymi kieszeniami na magnesy. Surowe minima/maksima i metadane są w
[benchmark.json](benchmark.json). To wyniki lokalne, nie gwarancja czasu
dla dowolnych modeli. Przy większych siatkach koszt rośnie z liczbą
trójkątów i stopek. Pierwsze uruchomienie po instalacji może być wyraźnie
dłuższe przez zimny cache systemu i tworzenie cache Pythona; powyższe
mediany dotyczą kolejnych uruchomień z dostępnymi plikami w cache.
