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
    opis: "7 cech otoczenia",
    kolor: "ostrzezenie",
    podkroki: [
      "Odległość do drogi i drogi utwardzonej",
      "Najbliższy budynek i zabudowa w 1 km",
      "Las w 500 m i usługi w 1 km",
      "Odległość do miasta 50 tys.+",
    ],
  },
  {
    numer: 4,
    nazwa: "Sąsiedztwo cenowe",
    opis: "7 cech z wcześniejszych transakcji",
    kolor: "rynek",
    podkroki: [
      "Transakcje w promieniu 2 i 5 km z 24 mies.",
      "Najbliższa wcześniejsza transakcja",
      "Mediany w obrębie i gminie",
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
