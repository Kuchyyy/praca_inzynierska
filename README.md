# Predykcja cen działek

Projekt inżynierski: wycena działek niezabudowanych w Polsce na podstawie
Rejestru Cen Nieruchomości (RCN) i danych OpenStreetMap.

## Struktura

- `backend/` — Python: przygotowanie danych, modele, baza PostGIS i serwer wyceny.
  Komendy uruchamiamy z katalogu `backend/`.
- `frontend/` — panel wyceny (React, Tailwind, shadcn). Opis: [frontend/README.md](frontend/README.md).
- `praca/` — dokumenty do pracy.
- `docker-compose.yml` i `.env` — w katalogu głównym.

```text
backend/
  main.py          kolejne etapy po kolei
  config.py        ścieżki, progi i przełączniki etapów
  modele.py        trening i ocena 5 modeli, zapis model.joblib (python modele.py)
  cechy.py         osobny skrypt: eksperymenty z cechami z config.EKSPERYMENTY, tabela w terminalu (python cechy.py)
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

`modele.py` to zwykły skrypt od góry do dołu (`python modele.py` albo etap 8 w `main.py`). Uczy pięć modeli na transakcjach przed `TEST_OD` (2025-01-01)
i ocenia je na transakcjach od tej daty. Zapisuje tylko jeden plik:
`db/dane/gotowe/model.joblib`. Wczytuje go `wycen_dzialke.py`, który podaje
cechy nowej działki nauczonym modelom (`predict`) dla serwera wyceny.

- Progi ceny za m² (0,1% i 99,8%) liczone są tylko na treningu i tak samo stosowane do testu.
- Jedno przygotowanie danych dla wszystkich modeli (`fit_transform` na treningu, `transform` na teście):
  powiat i gmina kodowane średnią log-ceny z treningu (`TargetEncoder`),
  pozostałe kategorie jako 0/1, liczby z medianą i wskaźnikiem braku.
- Regresje i drzewo uczą się na logarytmie ceny (`log_models`), las i boosting na cenie wprost.
- Wkład cech w wycenę: regresje liniowo względem średniej działki, drzewa przez SHAP.
- Ważność cech: wzrost MAE po przetasowaniu cechy na próbce testu.

Wyniki na teście (transakcje od 01.01.2025, zł/m²):

| Model | MAE | RMSE | R² | Mediana błędu względnego |
|---|---:|---:|---:|---:|
| Gradient Boosting | 65,28 | 240,7 | 0,394 | 36,1% |
| Random Forest | 69,90 | 233,0 | 0,432 | 41,6% |
| Decision Tree | 74,12 | 262,1 | 0,281 | 41,7% |
| Bayesian Ridge | 80,04 | 299,0 | 0,065 | 47,6% |
| Linear Regression | 80,03 | 299,0 | 0,065 | 47,6% |

Eksperymenty z cechami: `python cechy.py`. Lista jest w `config.py` (`EKSPERYMENTY`):
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
