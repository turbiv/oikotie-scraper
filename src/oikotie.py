from bs4 import BeautifulSoup
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from pathlib import Path
import time
import traceback
import json
import requests
from extractpdf import ExtractRentalPdf
from tqdm import tqdm
from uuid import uuid4
from dataclasses import dataclass, asdict
from typing import List


@dataclass
class RentalImages:
    data: List[bytes]
    id: str


@dataclass
class RentalProperty:
    id: str = None
    address: str = None
    postcode: str = None
    city: str = None
    district: str = None
    deposit: int = None

    building_type: str = None
    price: int = None
    balcony: bool = None
    floor: int = None
    floors: int = None
    size: int = None
    configuration: [] = None
    rooms: int = None
    elevator: bool = None
    year: int = None
    link: str = None
    heating: str = None
    land_ownership: str = None
    sauna: bool = None

    public_sauna: bool = None
    pets: bool = None

    images: RentalImages = None

    def dict(self):
        return {k: v for k, v in asdict(self).items()}

class Oikotie:

    def __init__(self, output_json: Path):
        self.base_url = "https://asunnot.oikotie.fi/vuokra-asunnot"
        self.driver_executable = Path(r"D:\__GIT\apartmentHunter\scraper\chromedriver.exe")
        self.driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))
        self.output_json = output_json
        self.output_pdf = Path(r"D:\__GIT\apartmentHunter\scraper\saved_pdf")

    def change_page(self, url: str):
        self.driver.get(url)
        time.sleep(2)
        content = self.driver.page_source
        soup = BeautifulSoup(content)
        return soup

    def savedataclass_json(self, dataclasses: list):
        save = []
        for data in dataclasses:
            data = data.dict()
            save.append(data)

        json_file = Path(self.output_json)
        with json_file.open("w", encoding="utf-8") as f:
            json.dump(save, f)

    def normalize_oikotie_table(self, table: dict):
        rental_property = RentalProperty()
        try:
            # Location
            location = table.get("sijainti")
            split_addr = location.split(",")
            rental_property.address = "".join(split_addr[:-1])

            split_addr = split_addr[-1].strip(" ").split(" ")
            rental_property.postcode = split_addr[0]
            rental_property.city = split_addr[1]

            rental_property.district = table.get("kaupunginosa")

            floor = table.get("kerros") # 6 / 6 or 6
            if floor:
                if floor.isdigit():
                    rental_property.floor = floor
                    rental_property.floors = table.get("kerroksia")
                else:
                    (first, second) = floor.replace(" ", "").split("/")
                    rental_property.floor = first
                    rental_property.floors = second

            rental_property.size = int(float(table.get("asuinpinta-ala").split(" ")[0].replace(",", ".")))

            configuration = table.get("huoneiston kokoonpano", "")
            configuration = configuration.replace(" ", "")
            rental_property.configuration = configuration.split(",") if "," in configuration else configuration.split("+")

            rooms = table.get("huoneita")
            if rooms:
                rental_property.rooms = int(rooms)

            rental_property.price = int("".join(filter(str.isdecimal, table.get("vuokra/kk", "").split(",")[0])))

            despoit = table.get("vakuus")
            if despoit:
                rental_property.deposit = int("".join(filter(str.isdecimal, despoit)))

            construction_year = table.get("rakennusvuosi")
            if construction_year:
                rental_property.year = int(construction_year)

            rental_property.building_type = table.get("rakennuksen tyyppi")
            rental_property.quality = table.get("kunto")
            rental_property.heating = table.get("lämmitys")
            rental_property.land_ownership = table.get("tontin omistus")

            balcony = table.get("parveke")
            if isinstance(balcony, str):
                rental_property.balcony = True if balcony == "kyllä" else False
            else:
                rental_property.balcony = False

            sauna = table.get("asunnossa sauna")
            if isinstance(sauna, str):
                rental_property.sauna = True if sauna == "kyllä" else False
            else:
                rental_property.sauna = False

            elevator = table.get("hissi")
            if isinstance(elevator, str):
                rental_property.elevator = True if elevator == "kyllä" else False
            else:
                rental_property.elevator = False

            rental_property.public_sauna = True if table.get("taloyhtiössä on sauna") else False
        except Exception as e:
            print(e)
            print(traceback.format_exc())

        return rental_property

    def get_rentals(self, city: str, latest: int = None):
        soup = self.change_page(f"{self.base_url}?pagination=1&locations=%5B%5B64,6,%22{city}%22%5D%5D&cardType=100")

        pagination = soup.find('pagination-indication')
        pages = pagination.find("span", attrs={'class':'ng-binding'}).text.split("/")[1]
        pages = int(pages)

        for page in tqdm(range(1, pages), desc="rental_pages"):
            new_url = f"{self.base_url}?pagination={page}&locations=%5B%5B64,6,%22{city}%22%5D%5D&cardType=100"
            print(new_url)

            soup = self.change_page(new_url)

            all_cards = [*soup.find_all('card-v2-default'), *soup.find_all('card-v2-plus')]
            for card in all_cards: # card-v2-text-container__title
                promotion_tag = card.find("div", text="Korostus")
                if promotion_tag:
                    print("Found promotional tag, skipping.")
                    continue

                link = card.find("a", attrs={'class':'ot-card-v2'})["href"]
                oikotie_id = link.split("/")[-1]
                res = requests.get(f"https://asunnot.oikotie.fi/nayttoesite/{oikotie_id}")

                try:
                    with ExtractRentalPdf(res.content) as pdf:
                        extracted_images = pdf.extract_img()
                        table = pdf.extract_tables()
                except Exception as e:
                    print("---------error----")
                    print(e)
                    print(traceback.format_exc())
                    continue

                if not table:
                    print("Failed to parse table")
                    continue

                rental_id = str(uuid4())

                rental_property = self.normalize_oikotie_table(table)
                rental_property.link = link
                rental_property.city = city
                rental_property.id = rental_id

                rental_property.images = RentalImages(extracted_images, rental_id)
                yield rental_property
