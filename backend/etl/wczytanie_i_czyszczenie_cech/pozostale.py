import numpy as np

# Jawny slownik RCN, wspolny dla calego kraju i obu zbiorow.
PRZEZNACZENIA = [
    "budownictwoMieszkanioweJednorodzinne",
    "terenRolniczy",
    "brakMPZPLubWZ",
    "terenZabudowyUslugowej",
    "terenDrogWewnetrznych",
    "innyNiewymieniony",
    "terenDrogPublicznych",
    "budownictwoMieszkanioweWielorodzinne",
    "terenZabudowyZagrodowejGospodarstwRolnych",
    "terenObiektowProdukcyjnychSkladowIMagazynow",
    "terenSportuIRekreacji",
    "las",
    "terenZieleniUrzadzonej",
    "obszarITerenGorniczy",
    "terenInfrastrukturyTechnicznej",
    "terenWodPowierzchniowychSrodladowych",
    "decyzjaWarunkiZabudowy",
    "terenZieleniObjetyFormaOchronyPrzyrody",
    "terenOgrodowDzialkowych",
    "terenObslugiProdukcjiWGospodarstwachRolnych",
    "terenKomunikacjiWodnejSzlakWodny",
    "terenRozmieszczeniaDuzcychObiektowHandlowych",
    "cmentarz",
    "terenWodPowierzchniowychMorskich",
]


def dodaj_pozostale(dane):
    dane = dane.copy()
    dane["log_powierzchnia"] = np.log(dane["powierzchnia_m2"])
    dane["miesiace_od_2015"] = (
        (dane["dok_data"].dt.year - 2015) * 12 + dane["dok_data"].dt.month - 1
    )
    dane["miejscowosc"] = (
        dane["dzi_adres"]
        .str.extract(r"(?:^|;)\s*MSC:([^;]+)")[0]
        .str.strip()
        .str.upper()
    )
    dane["miejscowosc"] = dane["miejscowosc"].replace("", None)
    dane["wskaznik_zwartosci"] = 4 * np.pi * dane["pole_geom_m2"] / dane["obwod_m"] ** 2
    dane["wskaznik_zwartosci"] = dane["wskaznik_zwartosci"].where(dane["obwod_m"].gt(0))

    wpisy = []
    for tekst in dane["dzi_przezn_wmpzp"].fillna(""):
        wpisy.append({czesc.strip() for czesc in tekst.split(";") if czesc.strip()})

    for kategoria in PRZEZNACZENIA:
        dane["przezn_" + kategoria] = [int(kategoria in wpis) for wpis in wpisy]

    dane["przezn_brak_danych"] = [int(not wpis) for wpis in wpisy]
    znane = set(PRZEZNACZENIA)
    dane["przezn_nieznana_kategoria"] = [int(bool(wpis - znane)) for wpis in wpisy]

    # To obecnosc informacji w RCN, nie potwierdzenie obowiazywania MPZP.
    dane["ma_wpis_przeznaczenia"] = [int(bool(wpis)) for wpis in wpisy]
    return dane
