import random
from config import *

class CommentaryEngine:
    def __init__(self):
        self.last_templates = []
        self.history_size = 10 # Track last 10 templates to avoid repetition
        
        self.templates = {
            EVENT_NOTHING: {
                "early_neutral": [
                    "Początek spotkania, obie drużyny badają się nawzajem.",
                    "Spokojne tempo w pierwszych minutach, nikt nie chce popełnić błędu.",
                    "Gra toczy się w środku pola, czekamy na pierwszą groźną akcję.",
                    "Obrońcy wymieniają podania, próbując wyciągnąć rywala z defensywy.",
                ],
                "mid_neutral": [
                    "Taktyczne szachy na murawie, trenerzy szukają luki w ustawieniu.",
                    "Piłka krąży od nogi do nogi, ale brakuje wykończenia.",
                    "Trochę niedokładności w środku pola, gra się rwie.",
                    "Walka o górną piłkę w kole środkowym, twarde starcie.",
                ],
                "late_neutral": [
                    "Zmęczenie daje o sobie znać, tempo nieco spadło.",
                    "Zegar tyka, a na boisku wciąż patowa sytuacja w tej akcji.",
                    "Próba długiego podania 'na aferę', ale obrońcy są czujni.",
                    "Końcówka meczu, nikt nie chce zaryzykować decydującego błędu.",
                ],
                "pressure": [
                    "{team} zamyka rywala na własnej połowie!",
                    "Kolejna fala ataku {team}, obrona rozpaczliwie się broni!",
                    "To jest oblężenie! {team} nie wypuszcza rywala z pola karnego.",
                    "Pachnie bramką! {team} naciska coraz mocniej!",
                    "Kibice {team} wstali z miejsc, czują, że gol wisi w powietrzu!",
                ],
                "chaos": [
                    "Kompletny chaos w polu karnym! Piłka odbija się jak w bilardzie!",
                    "Nikt nie panuje nad sytuacją, piłka lata nad głowami!",
                    "To nie jest futbol, to walka wręcz o każdą piłkę!",
                    "Sędzia traci kontrolę nad spotkaniem, robi się bardzo nerwowo!",
                ]
            },
            EVENT_ATTACK: [
                "{player} urywa się obrońcom, to może być groźna akcja!",
                "Świetny rajd {player} skrzydłem, ależ ma przyspieszenie!",
                "{team} wychodzi z zabójczą kontrą 3 na 2!",
                "Genialne prostopadłe podanie do {player}, ma autostradę do bramki!",
                "{player} mija rywala balansem ciała i wbiega w pole karne!",
                "Szybka klepka {team}, rozmontowują linię defensywy!",
            ],
            EVENT_SHOT: [
                "{player} składa się do strzału... UDERZENIE!",
                "Potężna bomba z dystansu w wykonaniu {player}!",
                "{player} próbuje technicznej podcinki nad bramkarzem!",
                "Krótki zwód i natychmiastowy strzał {player} w krótki róg!",
                "{player} uderza z pierwszej piłki, to była trudna pozycja!",
            ],
            EVENT_SAVE: [
                "Niewiarygodne! {player} wyjmuje piłkę z samego okienka!",
                "Robinsonada {player}! Co za interwencja, ratuje wynik!",
                "{player} wygrywa pojedynek sam na sam! Klasa światowa!",
                "To musiał być gol! Ale {player} mówi stanowcze NIE!",
                "{player} instynktownie broni nogami! Co za refleks!",
            ],
            EVENT_GOAL: [
                "⚽ GOOOOL! {player} wpisuje się na listę strzelców!",
                "⚽ ALEŻ TRAFIENIE! {player} zdejmuje pajęczynę z okienka!",
                "⚽ Stadiony świata! {player} daje prowadzenie drużynie {team}!",
                "⚽ Bramkarz bez szans! Precyzyjny strzał {player} ląduje w siatce!",
                "⚽ To jest nokaut! {player} bezlitośnie wykorzystuje błąd obrony!",
            ],
            EVENT_FOUL: [
                "Brzydki faul, {player} zdecydowanie przesadził z agresją.",
                "Gwizdek sędziego. {player} fauluje taktycznie, przerywając kontrę.",
                "Nieprzepisowe zagranie {player}, sędzia musiał to odgwizdać.",
            ],
            EVENT_YELLOW_CARD: [
                "🟨 Żółta kartka dla {player}. Zasłużona kara za ten faul.",
                "🟨 Sędzia nie ma wątpliwości, wyciąga żółty kartonik. {player} musi uważać.",
            ],
            EVENT_RED_CARD: [
                "🟥 CZERWONA KARTKA! {player} wylatuje z boiska! Dramat!",
                "🟥 Brutalne wejście {player} i sędzia bez wahania wyrzuca go z gry!",
            ],
            "meta": [
                "Mimo optycznej przewagi, {dominator} wciąż nie potrafi udokumentować tego golem.",
                "Wynik na tablicy nie do końca oddaje przebieg tego spotkania.",
                "To niesamowite, że wciąż mamy taki wynik przy tylu sytuacjach.",
            ]
        }

    def get_commentary(self, match, event_type, context=None):
        if match.mode == 'fast' and event_type not in [EVENT_GOAL, EVENT_RED_CARD]:
             return None

        # Determine sub-category for EVENT_NOTHING / Events
        options = []
        
        if event_type == EVENT_NOTHING:
            # Check phases and context
            if match.chaos_level > 0.6:
                options = self.templates[EVENT_NOTHING]["chaos"]
            elif (match.possession_streak > 1 or 
                  abs(match.home_team.momentum - match.away_team.momentum) > 20):
                options = self.templates[EVENT_NOTHING]["pressure"]
            else:
                # Time-based neutral
                if match.current_minute <= 30:
                    options = self.templates[EVENT_NOTHING]["early_neutral"]
                elif match.current_minute <= 70:
                    options = self.templates[EVENT_NOTHING]["mid_neutral"]
                else:
                    options = self.templates[EVENT_NOTHING]["late_neutral"]
        
        elif event_type == "meta":
             options = self.templates["meta"]
             
        else:
            # Standard events
            options = self.templates.get(event_type, [])

        if not options:
            return "..."

        # Filter used templates to avoid repetition
        valid_options = [t for t in options if t not in self.last_templates]
        if not valid_options:
            # If we ran out of unique ones, relax the constraint slightly (e.g. check last 5 instead of 10)
            valid_options = [t for t in options if t not in self.last_templates[-5:]]
            if not valid_options:
                 valid_options = options # Fallback reset

        template = random.choice(valid_options)
        
        # Remember usage
        self.last_templates.append(template)
        if len(self.last_templates) > self.history_size:
            self.last_templates.pop(0)

        # Context Formatting
        team_name = context.get('team').name if context and context.get('team') else "Drużyna"
        if not team_name and match.possession_team:
             team_name = match.possession_team.name # Fallback for neutral events
             
        player_name = context.get('player').name if context and context.get('player') else "Zawodnik"
        
        # Meta commentary helper vars
        dominator = match.home_team.name if match.home_team.momentum > match.away_team.momentum else match.away_team.name
        
        return template.format(
            team=team_name, 
            player=player_name, 
            dominator=dominator
        )
