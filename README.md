# Predykcja cen działek

Projekt inżynierski: wycena działek niezabudowanych w Polsce na podstawie
Rejestru Cen Nieruchomości (RCN) i danych OpenStreetMap.

## Struktura

- `backend/` — Python: przygotowanie danych, modele, baza PostGIS i serwer wyceny.
  Komendy uruchamiamy z katalogu `backend/`.
- `frontend/` — panel wyceny (React, Tailwind, shadcn). Opis: [frontend/README.md](frontend/README.md).
- `praca/` — diagramy do pracy (architektura, przypadki użycia).
- `docker-compose.yml` — w katalogu głównym. Baza działa lokalnie, bez haseł.

```text
backend/
  main.py                      kolejne etapy po kolei
  config.py                    ścieżki, progi i przełączniki etapów
  modele.py                    trening i ocena 5 modeli, zapis model.joblib
  waznosc_cech.py              ważność cech, dopisywana do model.joblib
  walidacja_kroczaca_modele.py walidacja krocząca na latach 2021–2024
  eksperymenty_cech.py         eksperymenty z pomijaniem grup cech
  wycen_dzialke.py             wczytuje nauczone modele; funkcja wycen() wycenia jedną działkę
  api.py                       serwer wyceny (FastAPI) dla panelu
  wycena/                      cechy działki liczone w PostGIS, historia cen, okolica
  etl/                         czyszczenie RCN, granice ULDK/EGiB, cechy OSM, sąsiedztwo cenowe
  db/                          import do PostGIS, Docker bazy, dane lokalne (poza Git)
```

## Uruchomienie

Potrzebny Python 3.12 i Node.js. Zapisany `model.joblib` był uczony w scikit-learn 1.8.0
i inna wersja może go nie wczytać.

```bash
cd backend
python3.12 -m venv ../.venv312
source ../.venv312/bin/activate
pip install -r requirements.txt
python main.py
```

`main.py` wykonuje etapy po kolei:

1. pobranie RCN i mapy OSM Polski (jeśli jeszcze ich nie ma),
2. czyszczenie transakcji RCN,
3. pobranie brakujących granic działek z ULDK i paczek EGiB (`UZUPELNIJ_ULDK`, `UZUPELNIJ_EGIB`),
4. ponowne czyszczenie z uzupełnionymi granicami,
5. 7 cech otoczenia z OSM,
6. cechy działki, przeznaczenie i 7 cech sąsiedztwa cenowego,
7. import do PostGIS (`IMPORTUJ_DO_BAZY`),
8. trening modeli (`TRENUJ_MODELE`), ważność cech (`WAZNOSC_CECH`), eksperymenty z cechami
   (`SYMULACJA_CECH`) i walidacja krocząca (`WALIDACJA_KROCZACA`).

Etap, którego plik wynikowy już istnieje, jest pomijany. Żeby go przeliczyć,
usuń jego plik. Etapy z przełącznikiem w `config.py` uruchamiamy ręcznie,
bo pobierają dane z sieci, zapisują do bazy albo długo liczą.
Granice z ULDK i EGiB trafiają do `db/dane/posrednie/uldk_granice.sqlite`,
więc przerwane pobieranie wznawia się od miejsca przerwania.
Nie uruchamiaj dwóch pobierań naraz.

Pojedynczy etap z podkatalogu uruchamiamy jako moduł, np. `python -m db.import_postgis`.

## Zasady czyszczenia

- Klucz transakcji to przestrzeń nazw i lokalny identyfikator. Transakcja musi mieć
  dokładnie jedną działkę i jedną spójną wersję wpisu.
- Zostają grunty niezabudowane, wolny rynek, daty od 2015 r. do `DATA_DO`.
- Udział musi być znany: pełny albo jeden ułamek z przedziału (0, 1).
  Cena za m² to `tran_cena_brutto / (powierzchnia_m2 * udzial_sprzedany)`.
- Powierzchnię sprawdzamy z polem granicy w EPSG:2180 (tolerancja 0,80–1,25).
  Brak granicy albo rozbieżność daje pustą powierzchnię i `do_modelu = false`.
- Do modelu trafiają działki 100–200 000 m² z poprawną ceną za m².

## Baza PostGIS, serwer i panel

```bash
docker compose up -d --build --wait db     # z katalogu głównego

cd backend
python api.py                              # http://127.0.0.1:8000

cd frontend                                # w drugim terminalu
npm install
npm run dev                                # http://localhost:5173
```

Opis bazy i połączenia: [backend/db/POSTGIS.md](backend/db/POSTGIS.md).
Serwer liczy dla wskazanej działki te same 51 cech co ETL, ale zapytaniami do PostGIS:
dane z formularza, granica, 7 cech OSM, 7 cech sąsiedztwa cenowego (tylko sprzedaże
sprzed daty wyceny), potem predykcje pięciu modeli i przedział 80%.

## Modele

Model dostaje 51 cech: transakcja (3), lokalizacja (2), położenie i kształt działki (4), czas (2),
OSM (7), przeznaczenie (26) i sąsiedztwo cenowe (7).

`modele.py` to zwykły skrypt od góry do dołu (`python modele.py` albo etap 8 w `main.py`). Działa w dwóch krokach:

1. Uczy pięć modeli na transakcjach do końca 2023 r. i ocenia je na walidacji, czyli sprzedażach z 2024 r.
   (`WALIDACJA_OD`). Tu wybiera najlepszy model i ustala przedział 80%.
2. Uczy te same modele na całym treningu (przed `TEST_OD`, 2025-01-01) i ocenia je na teście od tej daty.
   Test służy tylko do oceny i do sprawdzenia, ile prawdziwych cen mieści się w przedziale.

Zapisuje tylko jeden plik: `db/dane/gotowe/model.joblib`. Wczytuje go `wycen_dzialke.py`, który podaje
cechy nowej działki nauczonym modelom (`predict`) dla serwera wyceny.

- Progi ceny za m² (0,1% i 99,8%) liczone są tylko na treningu i tak samo stosowane do walidacji i testu.
- Jedno przygotowanie danych dla wszystkich modeli (`fit_transform` na części uczącej, `transform` na reszcie):
  liczby z medianą w miejsce braków, wskaźnikiem braku i skalowaniem, kategorie (w tym województwo i powiat) jako kolumny 0/1.
- Wszystkie modele uczą się na logarytmie ceny, a wynik jest obcinany do progów ceny z treningu.
  Bez tego regresja liniowa dawała czasem wyceny rzędu 10^21 zł/m², bo mediany cen z okolicy
  zawierają pojedyncze błędne ceny z RCN.
- Wkład cech w wycenę: regresje liniowo względem średniej działki, drzewa przez SHAP.
- Ważność cech: wzrost MAE po przetasowaniu cechy na próbce testu (`python waznosc_cech.py`).

Dane: 605 935 transakcji w treningu (w tym 84 407 z 2024 r. na walidację) i 124 516 w teście
(429 odrzuconych przez progi ceny).

Wyniki (zł/m²; walidacja: sprzedaże z 2024 r., test: od 01.01.2025):

| Model | MAE walidacja | MAE test | RMSE test | R² test | Mediana błędu względnego |
|---|---:|---:|---:|---:|---:|
| Gradient Boosting | 63,15 | 64,44 | 241,2 | 0,391 | 35,4% |
| Random Forest | 67,72 | 68,78 | 256,7 | 0,311 | 38,2% |
| Decision Tree | 72,84 | 74,07 | 262,4 | 0,280 | 41,8% |
| Bayesian Ridge | 82,54 | 81,82 | 287,1 | 0,138 | 48,2% |
| Linear Regression | 82,65 | 81,87 | 287,1 | 0,138 | 48,2% |

Na walidacji wygrywa Gradient Boosting i to on daje wycenę w panelu. Przedział 80% ustalony
na walidacji obejmuje na teście 79,6% prawdziwych cen:

| Transakcji w 2 km (24 mies.) | Transakcji w teście | Pokrycie |
|---|---:|---:|
| 0 | 5 621 | 77,3% |
| 1–9 | 55 917 | 79,5% |
| 10–29 | 46 541 | 79,6% |
| 30+ | 16 437 | 80,6% |

Walidacja krocząca (`python walidacja_kroczaca_modele.py`): uczenie na latach wcześniejszych, ocena na kolejnym
roku (2021–2024), cechy sąsiedztwa liczone od nowa dla każdego roku. Wynik to tabela MAE w terminalu.

Eksperymenty z cechami: `python eksperymenty_cech.py`. Lista jest w `config.py` (`EKSPERYMENTY`):
nazwa eksperymentu i grupy albo pojedyncze cechy, które pomijamy. Skrypt uczy Gradient Boosting
dla każdego eksperymentu i drukuje tabelę: liczba cech, MAE, zmiana MAE, mediana błędu.
Model główny zawsze używa wszystkich cech.

### Wybór cech OSM

Na początku było 27 cech z OpenStreetMap. Ważność cech pokazała, że liczą się głównie
odległość do budynku, odległość do drogi i liczba usług w 1 km, a reszta się dublowała
(budynki w 250/500/1000 m, kilka rodzajów miast i dróg) albo prawie nic nie wnosiła
(szkoła, autostrada, przystanek, woda).
Zostało 7 cech, każda odpowiada na inne pytanie: zabudowa obok, gęstość zabudowy, dojazd,
droga utwardzona, usługi, las, odległość do miasta 50 tys.+.

Modele wyceniają ceny transakcyjne z RCN, a nie ceny ofertowe z ogłoszeń.
