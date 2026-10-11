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
| `standard` | Profil standardowy bez otworów. |
| `rebuilt` | Profil Rebuilt i dolne kieszenie na magnesy; proste, bez żeber i bez dodatkowych mostków drukarskich. |
| `rebuilt-screws` | Jak `rebuilt`, dodatkowo otwory na śruby. Ich głębokość kończy się na wysokości cięcia, maksymalnie 7 mm. |
| `refined` | Kieszenie z bocznym wsuwaniem magnesu, podłogą i otworem do wypchnięcia; otwarcia kierują się na lewo/prawo od środka stopki. |
| `press-fit` | Dolne kieszenie z ośmioma żebrami zgniatanymi przy wciskaniu magnesu. |

Nazwy oznaczają konkretne konfiguracje tego narzędzia. `rebuilt` nie jest
kopią wszystkich aktualnych ustawień domyślnych Customizera upstream;
`refined` nie dodaje centralnego otworu na thumbscrew. Wszystkie presety
zachowują ten sam profil współpracy z płytą bazową. Są generowane lokalnie,
bez pobierania STL i bez uruchamiania OpenSCAD.

Źródła techniczne, z przypiętą rewizją `910e22d8607fd7f5f51ad5e5cbc5287a76810bfd`:

- [Rebuilt — standard.scad](https://github.com/kennetek/gridfinity-rebuilt-openscad/blob/910e22d8607fd7f5f51ad5e5cbc5287a76810bfd/src/core/standard.scad): profil, siatka, promienie i wymiary otworów.
- [Rebuilt — gridfinity-rebuilt-holes.scad](https://github.com/kennetek/gridfinity-rebuilt-openscad/blob/910e22d8607fd7f5f51ad5e5cbc5287a76810bfd/src/core/gridfinity-rebuilt-holes.scad): boczna kieszeń Refined oraz żebra kieszeni wciskanych.
- [Gridfinity Refined, grizzie17](https://www.printables.com/model/413761-gridfinity-refined): projekt przypisany w kodzie Rebuilt jako źródło Refined.
- [Katalog Gridfinity](https://github.com/jeffbarr/gridfinity-catalog): przegląd ekosystemu, w tym płyt bazowych.

Atrybucja i licencja źródłowej implementacji: [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
