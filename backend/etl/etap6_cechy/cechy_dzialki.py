import numpy as np

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

    rok = dane["dok_data"].dt.year
    miesiac = dane["dok_data"].dt.month
    dane["miesiace_od_2015"] = (rok - 2015) * 12 + miesiac - 1


    dane["wskaznik_zwartosci"] = 4 * np.pi * dane["pole_geom_m2"] / dane["obwod_m"] ** 2
    dane["wskaznik_zwartosci"] = dane["wskaznik_zwartosci"].where(dane["obwod_m"] > 0)

    wpisy = []
    for tekst in dane["dzi_przezn_wmpzp"].fillna(""):
        przeznaczenia_dzialki = []
        for czesc in tekst.split(";"):
            if czesc.strip() != "":
                przeznaczenia_dzialki.append(czesc.strip())
        wpisy.append(przeznaczenia_dzialki)

    for kategoria in PRZEZNACZENIA:
        kolumna = []
        for przeznaczenia_dzialki in wpisy:
            if kategoria in przeznaczenia_dzialki:
                kolumna.append(1)
            else:
                kolumna.append(0)
        dane["przezn_" + kategoria] = kolumna

    brak_danych = []
    ma_wpis = []
    for przeznaczenia_dzialki in wpisy:
        if len(przeznaczenia_dzialki) == 0:
            brak_danych.append(1)
            ma_wpis.append(0)
        else:
            brak_danych.append(0)
            ma_wpis.append(1)
    dane["przezn_brak_danych"] = brak_danych
    dane["ma_wpis_przeznaczenia"] = ma_wpis

    return dane
