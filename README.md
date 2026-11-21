# Predykcja cen działek

Projekt inżynierski: wycena działek niezabudowanych w Polsce na podstawie
Rejestru Cen Nieruchomości (RCN) i danych OpenStreetMap.

## Struktura

- `backend/` — Python: przygotowanie danych, modele, baza PostGIS i serwer wyceny.
  Komendy uruchamiamy z katalogu `backend/`.
- `frontend/` — panel wyceny (React, Tailwind, shadcn). Opis: [frontend/README.md](frontend/README.md).
- `praca/` — dokumenty do pracy.
- `docker-compose.yml` — w katalogu głównym. Baza działa lokalnie, bez haseł.

```text
backend/
  main.py          kolejne etapy po kolei
  config.py        ścieżki, progi i przełączniki etapów
  modele.py        trening i ocena 5 modeli, zapis model.joblib (python modele.py)
  eksperymenty_cech.py osobny skrypt: eksperymenty z cechami z config.EKSPERYMENTY, tabela w terminalu (python eksperymenty_cech.py)
  wycen_dzialke.py wczytuje nauczone modele; funkcja wycen() wycenia jedną działkę dla panelu
  api.py           serwer wyceny (FastAPI) dla panelu
  wycena/          cechy działki liczone w PostGIS, historia cen, okolica
  etl/             czyszczenie RCN, granice ULDK/EGiB, cechy OSM, sąsiedztwo cenowe
  db/              pobranie danych, import do PostGIS, Docker bazy
```

## Uruchomienie

Potrzebny Python 3.12.

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
6. cechy działki, przeznaczenie i 8 cech sąsiedztwa cenowego,
7. import do PostGIS (`IMPORTUJ_DO_BAZY`),
8. trening modeli (`TRENUJ_MODELE`) i symulacja cech (`SYMULACJA_CECH`).

Etap, którego plik wynikowy już istnieje, jest pomijany. Żeby go przeliczyć,
usuń jego plik. Etapy z przełącznikiem w `config.py` uruchamiamy ręcznie,
bo pobierają dane z sieci, zapisują do bazy albo długo liczą.
Granice z ULDK i EGiB trafiają do `db/dane/posrednie/uldk_granice.sqlite`,
więc przerwane pobieranie wznawia się od miejsca przerwania.
Nie uruchamiaj dwóch pobierań naraz.

## Zasady czyszczenia

- Klucz transakcji to przestrzeń nazw i lokalny identyfikator. Transakcja musi mieć
  dokładnie jedną działkę i jedną spójną wersję wpisu.
- Zostają grunty niezabudowane, wolny rynek, daty od 2015 r. do `DATA_DO`.
- Udział musi być znany: pełny albo jeden ułamek z przedziału (0, 1).
  Cena za m² to `tran_cena_brutto / (powierzchnia_m2 * udzial_sprzedany)`.
- Powierzchnię sprawdzamy z polem granicy w EPSG:2180 (tolerancja 0,80–1,25).
  Brak granicy albo rozbieżność daje pustą powierzchnię i `do_modelu = false`.
- Do modelu trafiają działki 100–200 000 m² z poprawną ceną za m².

## Baza PostGIS i panel

```bash
docker compose up -d --build --wait db     # z katalogu głównego
cd backend
python api.py                              # http://127.0.0.1:8000
```

Opis bazy i połączenia: [backend/db/POSTGIS.md](backend/db/POSTGIS.md).
Serwer liczy dla wskazanej działki te same 54 cechy co ETL, ale zapytaniami do PostGIS:
dane z formularza, granica, 7 cech OSM, 8 cech sąsiedztwa cenowego (tylko sprzedaże
sprzed daty wyceny), potem predykcje pięciu modeli i przedział 80%.

## Modele

`modele.py` to zwykły skrypt od góry do dołu (`python modele.py` albo etap 8 w `main.py`). Działa w dwóch krokach:

1. Uczy pięć modeli na transakcjach do końca 2023 r. i ocenia je na walidacji, czyli sprzedażach z 2024 r.
   (`WALIDACJA_OD`). Tu wybiera najlepszy model i ustala przedział 80%.
2. Uczy te same modele na całym treningu (przed `TEST_OD`, 2025-01-01) i ocenia je na teście od tej daty.
   Test służy tylko do oceny i do sprawdzenia, ile prawdziwych cen mieści się w przedziale.

Zapisuje tylko jeden plik: `db/dane/gotowe/model.joblib`. Wczytuje go `wycen_dzialke.py`, który podaje
cechy nowej działki nauczonym modelom (`predict`) dla serwera wyceny.

- Progi ceny za m² (0,1% i 99,8%) liczone są tylko na treningu i tak samo stosowane do walidacji i testu.
- Jedno przygotowanie danych dla wszystkich modeli (`fit_transform` na części uczącej, `transform` na reszcie):
  powiat i gmina kodowane średnią log-ceny (`TargetEncoder`),
  pozostałe kategorie jako 0/1, liczby z medianą i wskaźnikiem braku.
- Regresje i drzewo uczą się na logarytmie ceny (`log_models`), las i boosting na cenie wprost.
  Wynik modeli na logarytmie jest obcinany do progów ceny. Bez tego regresja liniowa dawała
  w walidacji kroczącej wyceny rzędu 10^21 zł/m², bo mediany cen z okolicy zawierają czasem błędne ceny z RCN.
- Wkład cech w wycenę: regresje liniowo względem średniej działki, drzewa przez SHAP.
- Ważność cech: wzrost MAE po przetasowaniu cechy na próbce testu (`python waznosc_cech.py`).

Wyniki (zł/m²; walidacja: sprzedaże z 2024 r., test: od 01.01.2025):

| Model | MAE walidacja | MAE test | RMSE test | R² test | Mediana błędu względnego |
|---|---:|---:|---:|---:|---:|
| Gradient Boosting | 63,88 | 65,28 | 240,7 | 0,394 | 36,1% |
| Random Forest | 69,49 | 69,90 | 233,0 | 0,432 | 41,6% |
| Decision Tree | 72,78 | 74,12 | 262,1 | 0,281 | 41,7% |
| Linear Regression | 79,65 | 79,35 | 275,0 | 0,209 | 47,6% |
| Bayesian Ridge | 79,65 | 79,35 | 275,0 | 0,209 | 47,6% |

Na walidacji wygrywa Gradient Boosting i to on daje wycenę w panelu. Przedział 80% ustalony
na walidacji obejmuje na teście 79,8% prawdziwych cen (od 78,2% przy braku transakcji w 2 km do 81,4% przy 30+).

Walidacja krocząca (`python walidacja_kroczaca_modele.py`): uczenie na latach wcześniejszych, ocena na kolejnym roku,
cechy sąsiedztwa liczone od nowa dla każdego roku. MAE w zł/m²:

| Model | 2021 | 2022 | 2023 | 2024 | Średnia |
|---|---:|---:|---:|---:|---:|
| Gradient Boosting | 46,92 | 49,02 | 57,90 | 65,39 | 54,81 |
| Random Forest | 47,77 | 51,03 | 61,98 | 69,32 | 57,52 |
| Decision Tree | 53,57 | 55,48 | 65,42 | 74,28 | 62,19 |
| Linear Regression | 55,60 | 58,47 | 75,19 | 80,74 | 67,50 |
| Bayesian Ridge | 55,61 | 58,46 | 75,19 | 80,75 | 67,50 |

Eksperymenty z cechami: `python eksperymenty_cech.py`. Lista jest w `config.py` (`EKSPERYMENTY`):
nazwa eksperymentu i grupy albo pojedyncze cechy, które pomijamy. Skrypt uczy Gradient Boosting
dla każdego eksperymentu i drukuje tabelę: liczba cech, MAE, zmiana MAE, mediana błędu.
Model główny zawsze używa wszystkich cech.

### Wybór cech OSM

Na początku było 27 cech z OpenStreetMap. Ważność cech pokazała, że liczą się głównie
odległość do budynku, odległość do drogi i liczba usług w 1 km, a reszta się dublowała
(budynki w 250/500/1000 m, kilka rodzajów miast i dróg) albo prawie nic nie wnosiła
(szkoła, autostrada, przystanek, woda, odległość do Wrocławia z etapu z samym Dolnym Śląskiem).
Zostało 7 cech, każda odpowiada na inne pytanie: zabudowa obok, gęstość zabudowy, dojazd,
droga utwardzona, usługi, las, odległość do miasta 50 tys.+.

Gradient Boosting na tym samym podziale (zł/m²):

| Wariant | Cech | MAE | R² | Mediana błędu |
|---|---:|---:|---:|---:|
| 27 cech OSM | 74 | 64,91 | 0,391 | 35,9% |
| 7 cech OSM | 54 | 65,41 | 0,387 | 36,1% |
| bez OSM | 47 | 67,54 | 0,365 | 37,9% |

Siedem cech zachowuje ok. 80% zysku z OSM przy czwartej części cech.

Modele wyceniają ceny transakcyjne z RCN, a nie ceny ofertowe z ogłoszeń.
