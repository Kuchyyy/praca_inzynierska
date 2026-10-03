# Styl kodu

Wzorem jest `model/pierwszy.py`.

- Pisz proste kroki od góry do dołu, zwykłe pętle i czytelne zmienne.
- `main.py` ma pokazywać kolejność etapów i wywoływać kod z odpowiednich plików.
- Ustawienia trzymaj w `config.py`, bez dokładania opcji `--...` do uruchamiania.
- Oddzielaj logiczne fragmenty pustą linią. Wcięcia: cztery spacje.
- Długie wyrażenia rozbijaj na nazwane kroki. Unikaj zbędnych zagnieżdżeń.
- Funkcje zostawiaj dla całych etapów lub współdzielonej logiki; nie twórz funkcji do każdego przypisania.
- Krótkie, naturalne komentarze tylko tam, gdzie coś wyjaśniają.
- Zachowaj przetwarzanie partiami, cache, kontrolę miejsca i możliwość wznowienia.
- Nie uruchamiaj drugiej kopii pobierania ULDK podczas działania pierwszej.
