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
| `rebuilt` | Kieszenie z bocznym wsuwaniem magnesu, podłogą i otworem do wypchnięcia; otwarcia kierują się na lewo/prawo od środka stopki. |
| `rebuilt-screws` | Jak `rebuilt`, dodatkowo otwory na śruby. Ich głębokość kończy się na wysokości cięcia, maksymalnie 7 mm. |
| `press-fit` | Dolne kieszenie z ośmioma żebrami zgniatanymi przy wciskaniu magnesu. |
| `refined` | Alias `rebuilt`: identyczna geometria z bocznym wsuwaniem magnesów. |
| `standard` | Alias `plain`: identyczna geometria bez otworów. |

`rebuilt` i `refined` korzystają z tej samej geometrii bocznych kieszeni
Rebuilt/Refined: szerokość 5,86 mm, wysokość 1,9 mm i podłoga 0,4 mm.
`rebuilt-screws` używa tych samych kieszeni z dodatkowymi otworami na śruby.
Starsze nazwy `refined` i `standard` pozostają obsługiwane jako aliasy.

Nazwy oznaczają konkretne konfiguracje tego narzędzia, bez centralnego
otworu na thumbscrew i pozostałych opcji Customizera upstream. Wszystkie presety
zachowują ten sam profil współpracy z płytą bazową. Są generowane lokalnie,
bez pobierania STL i bez uruchamiania OpenSCAD.

Źródła techniczne, z przypiętą rewizją `910e22d8607fd7f5f51ad5e5cbc5287a76810bfd`:

- [Rebuilt — standard.scad](https://github.com/kennetek/gridfinity-rebuilt-openscad/blob/910e22d8607fd7f5f51ad5e5cbc5287a76810bfd/src/core/standard.scad): profil, siatka, promienie i wymiary otworów.
- [Rebuilt — gridfinity-rebuilt-holes.scad](https://github.com/kennetek/gridfinity-rebuilt-openscad/blob/910e22d8607fd7f5f51ad5e5cbc5287a76810bfd/src/core/gridfinity-rebuilt-holes.scad): boczna kieszeń Refined oraz żebra kieszeni wciskanych.
- [Gridfinity Refined, grizzie17](https://www.printables.com/model/413761-gridfinity-refined): projekt przypisany w kodzie Rebuilt jako źródło Refined.
- [Katalog Gridfinity](https://github.com/jeffbarr/gridfinity-catalog): przegląd ekosystemu, w tym płyt bazowych.

Atrybucja i licencja źródłowej implementacji: [README](../README.md#license-and-attribution) i [LICENSE](../LICENSE).
