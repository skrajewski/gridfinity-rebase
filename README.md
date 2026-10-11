# Gridfinity Rebase

Szybkie CLI do podmiany podstawy standardowego bina Gridfinity w modelu STL. Przyjmuje model wejściowy
oraz STL dawcy albo nazwę presetu. Wynik to zamknięty, binarny STL w tych samych
współrzędnych. Silnik C++ Manifold wykonuje cięcie i łączenie bez OpenSCAD,
voxelizacji i przeliczania całej powierzchni przez Python.

## Uruchomienie

Python 3.10+ i [uv](https://docs.astral.sh/uv/):

```sh
uv sync
uv run gridfinity-rebase rebase tmp/gf_bin_1x1_h6_bin_v01.stl --preset rebuilt -o tmp/gf-rebuilt.stl
```

Instalacja jako zwykłe polecenie w terminalu:

```sh
uv tool install .
gridfinity-rebase --help
```

Alternatywnie: `python -m pip install .` w swoim środowisku Pythona.

## Podmiana podstawy

```sh
# Podstawa z drugiego modelu STL
uv run gridfinity-rebase rebase bin.stl \
  --base baza-1x1.stl -o wynik.stl

# Podstawa z presetu — działa offline
uv run gridfinity-rebase rebase tmp/gf_bin_1x1_h6_bin_v01.stl \
  --preset refined -o tmp/gf-refined.stl

# Lista presetów
uv run gridfinity-rebase presets

# Rozpoznanie standardowego bina, siatki i zalecanej wysokości cięcia
uv run gridfinity-rebase inspect tmp/gf_bin_1x1_h6_bin_v01.stl --json
```

Dostępne presety: `plain`, `rebuilt`, `rebuilt-screws`, `press-fit`.
`rebuilt` ma magnesy wsuwane z boku; `refined` jest jego aliasem.
`plain` nie ma otworów na magnesy ani śruby; `standard` jest jego aliasem.
Ich konfiguracje, źródła i kontekst popularności opisuje [docs/presets.md](docs/presets.md).

Bez `-o` wynik trafia do `NAZWA-rebased.stl`. Istniejący wynik wymaga
`--overwrite`. CLI chroni pliki wejściowe, również kiedy podasz jeden z nich
jako wynik. Zapisuje kompletny plik atomowo, po poprawnym zakończeniu obliczeń.

## Co dokładnie jest wymieniane

Domyślnie program **automatycznie rozpoznaje podstawę standardowego bina**.
Wymienia profil stopek oraz mostek/podłogę do nominalnych **7 mm**, zachowując
całą bryłę powyżej cięcia. Analizuje przekroje mostka i dopuszcza w nim typowe
okrągłe otwory śrub/magnesów oraz centralne otwory thumbscrew.

Jeśli wnętrze pojemnika zaczyna się poniżej lub na wysokości 7 mm, program
ustala jego początek przez dokładniejszą analizę przekrojów i cofa cięcie
o co najmniej 0,02 mm. Zaokrąglenia dna i scoop pozostają zachowane.
W referencji `tmp/gf_bin_1x1_h6_bin_v01.stl` automatyczne cięcie wypada na
**6,93 mm**. `inspect --json` pokazuje `standard_bin`, zalecaną wysokość cięcia
oraz przybliżony początek wnętrza.

Modele customowe wymagają jawnego wskazania zakresu wymiany:

```sh
uv run gridfinity-rebase rebase tmp/test.stl --preset plain \
  --base-height 4.75 -o tmp/custom-plain.stl
```

`--base-height` wyłącza automatyczny dobór wysokości i zastępuje wszystkie
detale poniżej wybranego poziomu. Musi wynosić co najmniej 4,75 mm.
Geometria **powyżej cięcia** zawsze pozostaje zachowana. Otwory śrub w
`rebuilt-screws` mają 3 mm średnicy i sięgają do wysokości cięcia, maksymalnie
7 mm. Geometria dawcy również jest kopiowana wyłącznie do tego poziomu.

Program automatycznie wyrównuje położenie dawcy w XYZ, bez skalowania.
Obsługuje dawcę o tej samej siatce, dawcę z zamienionymi wymiarami X/Y
(obrót 90°) oraz dawcę 1×1 powielanego na większej siatce. Przy pełnej podmianie
z dawcy 1×1 łączy stopki ciągłym mostkiem i kopiuje jego otwory do każdej komórki.
W trybie automatycznym również dawca musi mieć standardową podstawę, której
bezpieczny zakres sięga co najmniej do wybranej wysokości cięcia wejścia.

## Walidacja i obsługiwane modele

- Binarny i tekstowy STL, jednostki **mm**, stopki na dole, oś **Z w górę**.
- Standardowe biny z pełnym prostokątnym mostkiem, narożnikami o promieniu
  3,75 mm i stopkami na siatce 42 mm. Przesunięcie modelu, w tym ujemne Z,
  nie przeszkadza. Detale powyżej podstawy, przegrody i scoop są zachowane.
- Rozpoznawanie obejmuje przekroje na czterech wysokościach, rozstaw stopek,
  trzy odcinki profilu, szerokości i zaokrąglone narożniki. Sam wymiar
  obwiedni 41,5 mm nie wystarcza do uznania modelu za Gridfinity.
- Sprawdzamy obydwa modele, szczelność siatki, zgodność styku oraz przyłączenie
  nowych stopek. Błędny STL, zwykła bryła i płyta bazowa nie są przyjmowane.
- Brak pełnego standardowego mostka lub niejednoznaczna geometria w zakresie
  podstawy kończą podmianę błędem z prośbą o jawne `--base-height`; nie ma
  automatycznego powrotu do cięcia na 4,75 mm.

To rozpoznawanie geometrii, nie certyfikacja pochodzenia modelu. Tolerancja
szerokości i położenia przekrojów to 0,35 mm, aby przyjąć typowe eksporty STL.
Tryb manualny obsługuje też profil i warianty filletów z wcześniejszych przykładów. Half-grid,
nieregularne siatki, obrócone/pochylone modele i inne niestandardowe profile
należy wcześniej przekształcić; nie są automatycznie dopasowywane.

`--segments 32|64|128|256` kontroluje dokładność łuków w presetach (akceptowane
są też inne wielokrotności 8 w tym zakresie). Domyślne 64 segmenty dają
odchylenie od okręgu poniżej 0,005 mm przy promieniu 3,75 mm. Ta opcja nie
zmienia triangulacji podstawy kopiowanej z dawcy.

`--json` daje raport maszynowy. Kod wyjścia: `0` — sukces, `2` — błędne dane
lub argumenty. Błędy trafiają na stderr. `elapsed_ms` obejmuje pracę CLI od
wejścia do `main`, łącznie z importami silnika; nie obejmuje startu interpretera.

## Testy i pomiar szybkości

```sh
uv run pytest -q
uv run python scripts/benchmark.py --runs 5
```

Testy obejmują wszystkie presety, siatki 1×1 i 2×3, przesunięcia XYZ,
powielanie dawcy, obrót dawcy, zachowanie góry modelu, otwory, zamknięte puste
przestrzenie, automatyczne rozpoznanie dna, pełną wymianę otworów śrub,
ciągłość mostka z dawcy 1×1, szczelność eksportu, wadliwe STL i bezpieczne zapisy. Gdy przykłady
z `tmp` są dostępne, uruchamia się także regresja na rzeczywistych modelach.
Benchmark mierzy osobno silnik oraz cały proces CLI (start Pythona, odczyt,
walidacja, podmiana i zapis). Wyniki zależą od liczby trójkątów i komputera.
Lokalny pomiar obejmuje referencyjny `gf_bin_1x1` oraz model 6×6,
łącznie z automatycznym rozpoznaniem podstawy. Szczegóły, warunki pomiaru
i surowe wyniki: [docs/performance.md](docs/performance.md).

MIT. Atrybucja geometrii: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
