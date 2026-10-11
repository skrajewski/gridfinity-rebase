# Pomiar wydajności

Wykonano 11 października 2026, macOS 26.2 arm64, Python 3.11.14,
Manifold 3.5.4, NumPy 2.4.6. Każdy scenariusz uruchomiono 5 razy.

Komenda: `uv run python scripts/benchmark.py --runs 5 --json`.
Proces CLI uruchamiany jest jako osobny proces Pythona; pomiar obejmuje
start, importy, odczyt, walidację, automatyczne rozpoznanie podstawy,
podmianę i zapis STL. Kolumna silnika
obejmuje odczyt, walidację, automatyczne rozpoznanie podstawy, podmianę
i zapis po załadowaniu bibliotek,
z pamięcią podręczną pojedynczej stopki. Pliki pozostają w cache systemu.

| Scenariusz | Trójkąty wejścia | Cały proces, mediana | Silnik po rozgrzaniu, mediana |
| --- | ---: | ---: | ---: |
| example/plain | 7472 | 101.38 ms | 38.26 ms |
| example/rebuilt | 7472 | 108.53 ms | 40.16 ms |
| example/rebuilt-screws | 7472 | 131.42 ms | 55.53 ms |
| example/refined | 7472 | 108.46 ms | 39.41 ms |
| example/press-fit | 7472 | 108.18 ms | 40.14 ms |
| example/donor | 7472 | 107.02 ms | 43.12 ms |
| 6x6/refined | 58246 | 258.19 ms | 177.69 ms |

`example` to referencyjny `tmp/gf_bin_1x1_h6_bin_v01.stl`; `6x6` to wygenerowany pojemnik
z bocznymi kieszeniami na magnesy. Surowe minima/maksima i metadane są w
[benchmark.json](benchmark.json). To wyniki lokalne, nie gwarancja czasu
dla dowolnych modeli. Przy większych siatkach koszt rośnie z liczbą
trójkątów i stopek. Pierwsze uruchomienie po instalacji może być wyraźnie
dłuższe przez zimny cache systemu i tworzenie cache Pythona; powyższe
mediany dotyczą kolejnych uruchomień z dostępnymi plikami w cache.
