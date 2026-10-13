# Presety i źródła

Presety dotyczą **stopek pojemnika**, które wchodzą do gniazd Gridfinity.
Płyty bazowe („baseplates”, np. Clickfinity) są osobnymi częściami; wymiana
stopki nie zmienia płyty pod pojemnikiem.

Przegląd źródeł wykonano 11 października 2026. Rebuilt jest szeroko używaną
implementacją (około 2,3 tys. gwiazdek GitHub podczas przeglądu), a
[Vector76](https://github.com/vector76/gridfinity_openscad) opisuje odtworzenie
oryginału i opcjonalne kieszenie na magnesy/śruby. Nie istnieje tu wiarygodny,
globalny ranking popularności stopek. Wybraliśmy standardowe, rozpowszechnione
warianty opisane przez ich twórców, bez deklarowania rankingu pobrań.

| Preset | Geometria |
| --- | --- |
| `plain` | Profil standardowy bez otworów na magnesy i śruby. |
| `rebuilt` | Kieszenie z bocznym wsuwaniem magnesu, podłogą i otworem do wypchnięcia; otwarcia tworzą układ wachlarzowy, po jednym na każdą krawędź stopki. |
| `rebuilt-screws` | Jak `rebuilt`, dodatkowo otwory na śruby. Ich głębokość kończy się na wysokości cięcia, maksymalnie 7 mm. |
| `press-fit` | Dolne kieszenie z ośmioma żebrami zgniatanymi przy wciskaniu magnesu. |
| `refined` | Alias `rebuilt`: identyczna geometria z bocznym wsuwaniem magnesów. |
| `standard` | Alias `plain`: identyczna geometria bez otworów. |

`rebuilt` i `refined` korzystają z tej samej geometrii bocznych kieszeni
Rebuilt/Refined: szerokość 5,86 mm, wysokość 1,9 mm i podłoga 0,4 mm.
`rebuilt-screws` używa tych samych kieszeni z dodatkowymi otworami na śruby.
Starsze nazwy `refined` i `standard` pozostają obsługiwane jako aliasy.

Nazwy oznaczają konkretne konfiguracje tego narzędzia; pozostałe opcje
Customizera upstream nie są obsługiwane. Wszystkie presety
zachowują ten sam profil współpracy z płytą bazową. Są generowane lokalnie,
bez pobierania STL i bez uruchamiania OpenSCAD.

Źródła techniczne, z przypiętą rewizją `910e22d8607fd7f5f51ad5e5cbc5287a76810bfd`:

- [Rebuilt — standard.scad](https://github.com/kennetek/gridfinity-rebuilt-openscad/blob/910e22d8607fd7f5f51ad5e5cbc5287a76810bfd/src/core/standard.scad): profil, siatka, promienie i wymiary otworów.
- [Rebuilt — gridfinity-rebuilt-holes.scad](https://github.com/kennetek/gridfinity-rebuilt-openscad/blob/910e22d8607fd7f5f51ad5e5cbc5287a76810bfd/src/core/gridfinity-rebuilt-holes.scad): boczna kieszeń Refined oraz żebra kieszeni wciskanych.
- [Gridfinity Refined, grizzie17](https://www.printables.com/model/413761-gridfinity-refined): projekt przypisany w kodzie Rebuilt jako źródło Refined.
- [Katalog Gridfinity](https://github.com/jeffbarr/gridfinity-catalog): przegląd ekosystemu, w tym płyt bazowych.

Atrybucja i licencja źródłowej implementacji: [README](../README.md#license-and-attribution) i [LICENSE](../LICENSE).

## Independent geometry options

A preset is a shortcut to a group of settings. Settings are resolved in this
order: defaults (`plain`), the selected preset, then explicit flags. Running
`rebase` without a preset or donor generates a `plain` base.

- `--magnets none|side|bottom` selects the magnet pocket style.
- `--screws` and `--no-screws` enable or disable Ø3 mm screw bores,
  independently of magnets. Their depth is the cut height, up to 7 mm.
- `--crush-ribs` and `--no-crush-ribs` control ribs in bottom-loading pockets.


Omitted flags keep the preset's settings. `--magnets bottom` without a preset
generates smooth Ø6.5 mm pockets, 2.4 mm deep. Enabling ribs produces
`press-fit` geometry: eight ribs with a diameter range of 5.9–6.5 mm.
Explicit `--crush-ribs` requires `--magnets bottom`. Changing a preset's
magnet style to `none` or `side` clears inherited ribs; explicitly enabling
ribs with either style produces an error.

```sh
# Screws only
gridfinity-rebase rebase bin.stl --screws

# Side-loading magnet pockets and screw bores
gridfinity-rebase rebase bin.stl --magnets side --screws

# Ribbed bottom-loading pockets and screw bores
gridfinity-rebase rebase bin.stl --preset press-fit --screws

# Bottom-loading pockets without ribs
gridfinity-rebase rebase bin.stl --magnets bottom --no-crush-ribs

# Override a preset setting
gridfinity-rebase rebase bin.stl --preset rebuilt-screws --no-screws
```

Existing preset commands keep their geometry and output filenames.
Modified configurations receive a descriptive filename, such as
`bin-rebased-screws.stl` or `bin-rebased-magnets-bottom-crush-ribs-screws.stl`.
The JSON report includes a `geometry` object with the resolved `magnets`,
`screws` and `crush_ribs` settings. The `base`
field identifies the starting preset (default: `plain`) or donor path.

With `--base`, all explicit geometry flags, including disabling flags, are
rejected: the tool copies the donor geometry. The `geometry` field is `null`.

## Central thumbscrew thread

`--thumbscrew` adds a central, right-handed M15×1.5 threaded hole to every
foot of a generated base, matching the Gridfinity Refined implementation in
Rebuilt. For a base with side-loading magnets:

```sh
gridfinity-rebase rebase bin.stl --preset refined --thumbscrew
```

The hole is 4.75 mm deep and ends at the top of the foot profile; the bridge
above remains solid. Its geometry follows `_base_thumbscrew()` and
`ScrewThread()`: nominal M15×1.5, a 60° tooth angle, a 0.4 mm tolerance
parameter, a 15.65 mm tool diameter and a 0.1 mm shrinkage correction
(maximum hole diameter: 15.75 mm). `--segments` sets the thread resolution
along with the other curves. A compatible baseplate and Refined thumbscrew
are required; the CLI generates the hole, not those separate parts.

The option also works without `--preset`. With `--base`, donor holes are
copied unchanged. For an otherwise unmodified preset, the output filename
is `bin-rebased-PRESET-thumbscrew.stl`. The report's top-level `thumbscrew`
field is `true` or `false` for generated bases and `null` for donors, because
the tool does not identify a donor's mounting style.

## Outer-corner placement

- `--only-corners` limits magnet pockets and Ø3 mm screw bores to the four
  outer corners of the whole bin, regardless of grid size. It applies to
  side-loading pockets (including removal slots) and bottom-loading pockets,
  with or without ribs. A 1×1 bin keeps all four holes; 1×N and N×1 grids
  keep two at each end.

`--only-corners` selects hole positions without enabling magnets or screws
by itself. The output filename receives an `-only-corners` suffix, such as
`bin-rebased-rebuilt-screws-only-corners.stl`. Central `--thumbscrew` holes
still appear in every foot.
