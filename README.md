# Gridfinity Rebase

Szybkie CLI do podmiany stopki Gridfinity w modelu STL. Przyjmuje model wejściowy
oraz STL dawcy albo nazwę presetu. Wynik to zamknięty, binarny STL w tych samych
współrzędnych. Silnik C++ Manifold wykonuje cięcie i łączenie bez OpenSCAD,
voxelizacji i przeliczania całej powierzchni przez Python.

## Uruchomienie

Python 3.10+ i [uv](https://docs.astral.sh/uv/):

```sh
uv sync
uv run gridfinity-rebase rebase tmp/test.stl --preset rebuilt -o tmp/result.stl
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
uv run gridfinity-rebase rebase tmp/test.stl \
  --base tmp/test-rebased.stl -o tmp/from-donor.stl

# Podstawa z presetu — działa offline
uv run gridfinity-rebase rebase tmp/test.stl \
  --preset refined -o tmp/from-refined.stl

# Lista presetów
uv run gridfinity-rebase presets

# Rozpoznanie siatki i walidacja STL, bez zmian w pliku
uv run gridfinity-rebase inspect tmp/test.stl --json
```

Dostępne presety: `standard`, `rebuilt`, `rebuilt-screws`, `refined`, `press-fit`.
Ich konfiguracje, źródła i kontekst popularności opisuje [docs/presets.md](docs/presets.md).

Bez `-o` wynik trafia do `NAZWA-rebased.stl`. Istniejący wynik wymaga
`--overwrite`. CLI chroni pliki wejściowe, również kiedy podasz jeden z nich
jako wynik. Zapisuje kompletny plik atomowo, po poprawnym zakończeniu obliczeń.

## Co dokładnie jest wymieniane

Domyślne cięcie przebiega **4,75 mm powyżej najniższego punktu modelu** — obejmuje
profil stopek. Cała bryła powyżej tego poziomu jest zachowana z dokładnością
obliczeń siatki. Nie wymuszamy 7 mm: w przykładzie `tmp/test.stl` detale użytkowe
zaczynają się już przy 6,53 mm.

Możesz świadomie wymienić również mostek/podłogę:

```sh
uv run gridfinity-rebase rebase model.stl --preset rebuilt-screws \
  --base-height 7 -o result.stl
```

`--base-height` zwiększa zakres wymiany, więc zastępuje też wszystkie detale
poniżej wybranego poziomu. Kieszenie lub otwory starej podstawy **powyżej cięcia**
pozostają; ich usunięcie wymaga zwiększenia wysokości cięcia. Otwory śrub w
`rebuilt-screws` mają 3 mm średnicy i sięgają do wysokości cięcia, maksymalnie
7 mm; przy domyślnym cięciu kończą się na 4,75 mm. Geometria dawcy również jest
kopiowana wyłącznie do tego poziomu.

Program automatycznie wyrównuje położenie dawcy w XYZ, bez skalowania.
Obsługuje dawcę o tej samej siatce, dawcę z zamienionymi wymiarami X/Y
(obrót 90°), a przy cięciu 4,75 mm także stopkę dawcy 1×1 powielaną na większej
siatce. Dla pełnego mostka użyj dawcy o pasujących wymiarach lub presetu.

## Walidacja i obsługiwane modele

- Binarny i tekstowy STL, jednostki **mm**, stopki na dole, oś **Z w górę**.
- Pełne prostokątne siatki stopek o skoku 42 mm. Przesunięcie modelu, w tym
  ujemne Z, nie przeszkadza; ściany i obiekty nad podstawą mogą wystawać poza siatkę.
- Rozpoznawanie obejmuje przekroje na czterech wysokościach, rozstaw stopek,
  trzy odcinki profilu, szerokości i zaokrąglone narożniki. Sam wymiar
  obwiedni 41,5 mm nie wystarcza do uznania modelu za Gridfinity.
- Sprawdzamy obydwa modele, szczelność siatki, zgodność styku oraz przyłączenie
  nowych stopek. Błędny STL, zwykła bryła i płyta bazowa nie są przyjmowane.

To rozpoznawanie geometrii, nie certyfikacja pochodzenia modelu. Tolerancja
szerokości i położenia przekrojów to 0,35 mm, aby przyjąć typowe eksporty STL.
Standardowy profil i warianty filletów z przykładów są obsługiwane. Half-grid,
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
przestrzenie, szczelność eksportu, wadliwe STL i bezpieczne zapisy. Gdy przykłady
z `tmp` są dostępne, uruchamia się także regresja na rzeczywistych modelach.
Benchmark mierzy osobno silnik oraz cały proces CLI (start Pythona, odczyt,
walidacja, podmiana i zapis). Wyniki zależą od liczby trójkątów i komputera.

MIT. Atrybucja geometrii: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
