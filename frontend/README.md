# Panel wyceny działek

Jedna strona w trzech stanach, jak w Figmie:

1. **Dane działki** — mapa i formularz. Klik na mapie wybiera działkę, użytkownik uzupełnia
   przeznaczenie, prawo, sprzedającego i rodzaj gruntu. „Wyceń” działa dopiero przy komplecie.
2. **Liczenie** — proces krok po kroku na płótnie, bez wyników. Postęp i czasy kroków
   przychodzą na żywo z backendu.
3. **Wynik** — proces zwinięty w pasek, pod nim mapa z transakcjami z okolicy, cena
   z przedziałem 80%, porównanie pięciu modeli, wpływ cech, tabela wszystkich 74 cech
   z trybem „co jeśli”, historia cen w gminie i słownik cech.

Przycisk „Cechy” w nagłówku przełącza stronę na opis wszystkich 74 cech: co oznaczają,
jak są liczone, gdzie powstają w kodzie, statystyki z treningu, ważność w każdym modelu
i, po wycenie, wartość oraz wkład dla działki. Powrót nie gubi wyceny ani zmian w tabeli cech.

Wszystkie liczby liczy serwer wyceny `backend/api.py`: cechy działki w PostGIS,
sąsiedztwo cenowe z transakcji RCN i wytrenowane modele. W panelu nie ma już danych
przykładowych.

## Uruchomienie

Najpierw baza i serwer wyceny (z katalogu głównego):

```bash
docker compose up -d --wait db
cd backend
../.venv312/bin/python api.py
```

Potem panel w drugim terminalu:

```bash
cd frontend
npm install
npm run dev
```

Panel działa pod `http://localhost:5173`. Vite przekazuje zapytania `/api` do
`http://127.0.0.1:8000`. Mapa pobiera podkład z OpenFreeMap, a granice działek z ULDK,
więc potrzebuje internetu.

## Sprawdzenie

```bash
npm run lint
npm run build
```

## Struktura

- `src/App.tsx` — stan strony, wycena przez API i tryb „co jeśli”.
- `src/lib/api.ts` — zapytania do serwera wyceny (wycena strumieniowa, przeliczenie, podpowiedź).
- `src/komponenty/` — moduły panelu (formularz, proces, mapa, wynik, cechy, słownik…).
- `src/dane/slowniki.ts` — opcje formularza z kodami RCN.
- `src/dane/kroki.ts` — opisy sześciu kroków wyceny, zgodne z `backend/api.py`.
- `src/dane/opisyCech.ts` — opisy 74 cech: co to, po co, kroki liczenia, wzór, plik i funkcja, ograniczenia.
- `src/komponenty/OpisCech.tsx` — widok „Opis cech” ze spisem treści i statystykami z `GET /api/model`.
- `src/typy.ts` — typy danych zwracanych przez backend.
- `src/components/ui/` — komponenty shadcn (Base UI), dopasowane do motywu.
- `src/index.css` — kolory, font i zaokrąglenia z Figmy.
