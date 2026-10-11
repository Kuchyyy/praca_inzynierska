// Kroki wyceny w tej samej kolejności co w backend/api.py. Podkroki odpowiadają
// zdarzeniom „podkrok”, które backend wysyła po każdej grupie obliczeń.

import type { KrokProcesu } from "@/typy"

export const KROKI: KrokProcesu[] = [
  {
    numer: 1,
    nazwa: "Dane działki",
    opis: "Z formularza",
    kolor: "sukces",
    podkroki: ["Sprawdzono komplet wymaganych pól", "TERYT, data wyceny i przeznaczenie"],
  },
  {
    numer: 2,
    nazwa: "Granica działki",
    opis: "Pole i kształt z granicy",
    kolor: "akcja",
    podkroki: ["Przeliczono granicę na układ EPSG:2180", "Środek, pole, obwód i wskaźnik zwartości"],
  },
  {
    numer: 3,
    nazwa: "Cechy OSM",
    opis: "27 cech otoczenia",
    kolor: "ostrzezenie",
    podkroki: [
      "Odległości do dróg, przystanków i węzłów",
      "Zabudowa w promieniu 250, 500 i 1000 m",
      "Las, woda, szkoły i sklepy",
      "Miejscowości, miasta i granica państwa",
    ],
  },
  {
    numer: 4,
    nazwa: "Sąsiedztwo cenowe",
    opis: "8 cech z wcześniejszych transakcji",
    kolor: "rynek",
    podkroki: [
      "Transakcje w promieniu 2 i 5 km z 24 mies.",
      "Najbliższa wcześniejsza transakcja",
      "Mediany w obrębie i gminie, trend 12 mies.",
    ],
  },
  {
    numer: 5,
    nazwa: "Modele",
    opis: "5 modeli na tych samych cechach",
    kolor: "model",
    podkroki: ["Linear Regression", "Bayesian Ridge", "Decision Tree", "Random Forest", "Gradient Boosting"],
  },
  {
    numer: 6,
    nazwa: "Wynik",
    opis: "Cena i wyjaśnienie",
    kolor: "wynik",
    podkroki: ["Przedział 80%", "Wkład cech w wycenę", "Historia cen i transakcje w okolicy", "Cechy na tle gminy"],
  },
]
