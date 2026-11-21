export const RODZAJE_GRUNTU = [
  { kod: "gruntyRolne", nazwa: "Grunty rolne" },
  { kod: "gruntyZabudowaneIZurbanizowane", nazwa: "Grunty zabudowane i zurbanizowane" },
  { kod: "gruntyLesne", nazwa: "Grunty leśne" },
  { kod: "terenyKomunikacyjne", nazwa: "Tereny komunikacyjne" },
  { kod: "inne", nazwa: "Inne" },
]

export const PRAWA = [
  { kod: "wlasnoscNieruchomosciGruntowej", nazwa: "Własność" },
  { kod: "uzytkowanieWieczyste", nazwa: "Użytkowanie wieczyste" },
]

export const SPRZEDAJACY = [
  { kod: "osobaFizyczna", nazwa: "Osoba fizyczna" },
  { kod: "osobaPrawna", nazwa: "Firma" },
  { kod: "jednostkaSamorzaduTerytorialnego", nazwa: "Gmina" },
  { kod: "skarbPanstwa", nazwa: "Skarb Państwa" },
]

export const PRZEZNACZENIA = [
  {
    grupa: "Zabudowa mieszkaniowa",
    opcje: [
      { kod: "budownictwoMieszkanioweJednorodzinne", nazwa: "Zabudowa jednorodzinna" },
      { kod: "budownictwoMieszkanioweWielorodzinne", nazwa: "Zabudowa wielorodzinna" },
      { kod: "terenZabudowyZagrodowejGospodarstwRolnych", nazwa: "Zabudowa zagrodowa" },
    ],
  },
  {
    grupa: "Usługi i produkcja",
    opcje: [
      { kod: "terenZabudowyUslugowej", nazwa: "Zabudowa usługowa" },
      { kod: "terenObiektowProdukcyjnychSkladowIMagazynow", nazwa: "Produkcja, składy i magazyny" },
      { kod: "terenRozmieszczeniaDuzcychObiektowHandlowych", nazwa: "Duże obiekty handlowe" },
      { kod: "terenObslugiProdukcjiWGospodarstwachRolnych", nazwa: "Obsługa produkcji rolnej" },
      { kod: "terenInfrastrukturyTechnicznej", nazwa: "Infrastruktura techniczna" },
      { kod: "obszarITerenGorniczy", nazwa: "Teren górniczy" },
    ],
  },
  {
    grupa: "Rolne i leśne",
    opcje: [
      { kod: "terenRolniczy", nazwa: "Teren rolniczy" },
      { kod: "las", nazwa: "Las" },
    ],
  },
  {
    grupa: "Zieleń i rekreacja",
    opcje: [
      { kod: "terenSportuIRekreacji", nazwa: "Sport i rekreacja" },
      { kod: "terenZieleniUrzadzonej", nazwa: "Zieleń urządzona" },
      { kod: "terenZieleniObjetyFormaOchronyPrzyrody", nazwa: "Zieleń chroniona" },
      { kod: "terenOgrodowDzialkowych", nazwa: "Ogrody działkowe" },
      { kod: "cmentarz", nazwa: "Cmentarz" },
    ],
  },
  {
    grupa: "Komunikacja i wody",
    opcje: [
      { kod: "terenDrogPublicznych", nazwa: "Droga publiczna" },
      { kod: "terenDrogWewnetrznych", nazwa: "Droga wewnętrzna" },
      { kod: "terenKomunikacjiWodnejSzlakWodny", nazwa: "Szlak wodny" },
      { kod: "terenWodPowierzchniowychSrodladowych", nazwa: "Wody śródlądowe" },
      { kod: "terenWodPowierzchniowychMorskich", nazwa: "Wody morskie" },
    ],
  },
  {
    grupa: "Bez planu miejscowego",
    opcje: [
      { kod: "brakMPZPLubWZ", nazwa: "Brak planu i decyzji WZ" },
      { kod: "decyzjaWarunkiZabudowy", nazwa: "Decyzja o warunkach zabudowy" },
      { kod: "innyNiewymieniony", nazwa: "Inne, niewymienione" },
    ],
  },
]

export function nazwaOpcji(lista: { kod: string; nazwa: string }[], kod: string) {
  const opcja = lista.find((o) => o.kod === kod)
  return opcja ? opcja.nazwa : kod
}

export function nazwaPrzeznaczenia(kod: string) {
  for (const grupa of PRZEZNACZENIA) {
    const opcja = grupa.opcje.find((o) => o.kod === kod)
    if (opcja) {
      return opcja.nazwa
    }
  }
  return kod
}
