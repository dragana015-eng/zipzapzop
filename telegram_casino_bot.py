import json
import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# Konfiguracija
BOT_TOKEN = "8491156733:AAENpvLaK_yI4bOjC_o9V5bYX2X2MvCjrlg"  # Zameni sa svojim bot tokenom
ADMIN_ID = 8194376702  # Zameni sa svojim Telegram ID-om
DATA_FILE = "data.json"

# House edge konfiguracija
HOUSE_EDGE = 0.1  # 7% house edge
RIGGING_PROBABILITY = 0.37  # 25% šanse za rigging (za postizanje house edge-a)

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class CasinoBot:
    def __init__(self):
        self.data = self.load_data()

    def load_data(self) -> Dict[str, Any]:
        """Učitava podatke iz JSON fajla"""
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Proveri da li postoje svi potrebni ključevi i dodaj ih ako ne postoje
                self._ensure_data_structure(data)
                return data
        except FileNotFoundError:
            # Kreiranje osnovnih podataka ako fajl ne postoji
            return self._create_default_data()
        except json.JSONDecodeError:
            logger.error("JSON file is corrupted, creating new one")
            return self._create_default_data()

    def _create_default_data(self) -> Dict[str, Any]:
        """Kreira osnovnu strukturu podataka"""
        default_data = {
            "users": {},
            "house_balance": 100000,
            "cashout_requests": {},
            "game_history": [],
            "stats": {
                "blackjack": {"games": 0, "profit": 0},
                "roulette": {"games": 0, "profit": 0},
                "dice": {"games": 0, "profit": 0},
                "coinflip": {"games": 0, "profit": 0}
            },
            "broadcast_history": [],
            "work_cooldowns": {}
        }
        self.save_data(default_data)
        return default_data

    def _ensure_data_structure(self, data: Dict[str, Any]) -> None:
        """Osigurava da postoje svi potrebni ključevi u podatkovnoj strukturi"""
        if "users" not in data:
            data["users"] = {}
        if "house_balance" not in data:
            data["house_balance"] = 100000
        if "cashout_requests" not in data:
            data["cashout_requests"] = {}
        if "game_history" not in data:
            data["game_history"] = []
        if "broadcast_history" not in data:
            data["broadcast_history"] = []
        if "work_cooldowns" not in data:
            data["work_cooldowns"] = {}
        if "stats" not in data:
            data["stats"] = {
                "blackjack": {"games": 0, "profit": 0},
                "roulette": {"games": 0, "profit": 0},
                "dice": {"games": 0, "profit": 0},
                "coinflip": {"games": 0, "profit": 0}
            }

        # Proveri da postoje svi game stats
        for game in ["blackjack", "roulette", "dice", "coinflip"]:
            if game not in data["stats"]:
                data["stats"][game] = {"games": 0, "profit": 0}
            if "games" not in data["stats"][game]:
                data["stats"][game]["games"] = 0
            if "profit" not in data["stats"][game]:
                data["stats"][game]["profit"] = 0

        # Osiguraj da svaki korisnik ima potrebne podatke
        for user_id, user_data in data["users"].items():
            if "balance" not in user_data:
                user_data["balance"] = 0
            if "username" not in user_data:
                user_data["username"] = ""
            if "total_wagered" not in user_data:
                user_data["total_wagered"] = 0
            if "total_won" not in user_data:
                user_data["total_won"] = 0
            if "last_work" not in user_data:
                user_data["last_work"] = None

    def save_data(self, data: Dict[str, Any] = None) -> None:
        """Čuva podatke u JSON fajl"""
        if data is None:
            data = self.data
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving data: {e}")

    def get_user_balance(self, user_id: int) -> int:
        """Vraća balans korisnika"""
        user_id = str(user_id)
        if user_id not in self.data["users"]:
            self.data["users"][user_id] = {
                "balance": 0,  # Početni balans
                "username": "",
                "total_wagered": 0,
                "total_won": 0,
                "last_work": None
            }
            self.save_data()
        return self.data["users"][user_id]["balance"]

    def update_balance(self, user_id: int, amount: int) -> int:
        """Ažurira balans korisnika"""
        user_id = str(user_id)
        if user_id not in self.data["users"]:
            self.get_user_balance(int(user_id))  # Kreiranje korisnika

        self.data["users"][user_id]["balance"] += amount
        new_balance = self.data["users"][user_id]["balance"]

        # Ažuriranje house balance-a
        self.data["house_balance"] -= amount

        # Ažuriranje total_won ako je amount pozitivan
        if amount > 0:
            self.data["users"][user_id]["total_won"] += amount

        self.save_data()
        return new_balance

    def update_wager(self, user_id: int, amount: int) -> None:
        """Ažurira ukupan iznos opklada"""
        user_id = str(user_id)
        if user_id not in self.data["users"]:
            self.get_user_balance(int(user_id))

        self.data["users"][user_id]["total_wagered"] += amount
        self.save_data()

    def update_stats(self, game: str, profit: int) -> None:
        """Ažurira statistike igre"""
        try:
            self._ensure_data_structure(self.data)

            if game in self.data["stats"]:
                self.data["stats"][game]["games"] += 1
                self.data["stats"][game]["profit"] += profit
                self.save_data()
        except Exception as e:
            logger.error(f"Error updating stats: {e}")

    def log_game_result(self, user_id: int, game: str, bet: int, result: str, payout: int, rigged: bool = False) -> None:
        """Loguje rezultat igre"""
        try:
            self.data["game_history"].append({
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "game": game,
                "bet": bet,
                "result": result,
                "payout": payout,
                "rigged": rigged
            })

            # Čuvamo samo posledjih 1000 rezultata
            if len(self.data["game_history"]) > 1000:
                self.data["game_history"] = self.data["game_history"][-1000:]

            self.save_data()
        except Exception as e:
            logger.error(f"Error logging game result: {e}")

    def can_work(self, user_id: int) -> tuple[bool, Optional[datetime]]:
        """Proverava da li korisnik može da radi"""
        user_id = str(user_id)
        if user_id not in self.data["users"]:
            return True, None

        last_work = self.data["users"][user_id].get("last_work")
        if not last_work:
            return True, None

        try:
            last_work_time = datetime.fromisoformat(last_work)
            next_work_time = last_work_time + timedelta(days=3)

            if datetime.now() >= next_work_time:
                return True, None
            else:
                return False, next_work_time
        except:
            return True, None

    def set_work_time(self, user_id: int) -> None:
        """Postavlja vreme poslednjeg rada"""
        user_id = str(user_id)
        if user_id not in self.data["users"]:
            self.get_user_balance(int(user_id))

        self.data["users"][user_id]["last_work"] = datetime.now().isoformat()
        self.save_data()

    def get_all_users(self) -> List[int]:
        """Vraća listu svih user ID-ova"""
        return [int(user_id) for user_id in self.data["users"].keys()]

    def is_rigged_game(self) -> bool:
        """Određuje da li je igra rigged na osnovu house edge-a"""
        return random.random() < RIGGING_PROBABILITY

# Kreiranje instance bota
casino = CasinoBot()

# Komanda /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start komanda sa pozdravom i prikazom balansa"""
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username or "Nepoznat"

        # Čuvanje username-a
        if str(user_id) not in casino.data["users"]:
            casino.data["users"][str(user_id)] = {}
        casino.data["users"][str(user_id)]["username"] = username

        balance = casino.get_user_balance(user_id)

        welcome_text = f"""
🎰 **Dobrodošli u Casino Bot!** 🎰

Pozdrav {username}!
💰 Vaš trenutni balans: **{balance:,} RSD**

**Dostupne igre:**
🃏 /play <ulog> - Blackjack
🎲 /roulette <ulog> - Rulet
🎲 /dice <ulog> <brojevi> - Dice (1-3 broja)
🪙 /flip <ulog> <heads/tails> - Coinflip

**Ostale komande:**
💳 /bal - Proveri balans
💼 /work - Radi za 30 RSD (svaka 3 dana)
💸 /cashout <iznos> - Zatraži isplatu
❓ /help - Pomoć

**
        """

        await update.message.reply_text(welcome_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in start_command: {e}")
        await update.message.reply_text("❌ Došlo je do greške. Molimo pokušajte ponovo.")

# Komanda /bal
async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prikazuje balans korisnika"""
    try:
        user_id = update.effective_user.id
        balance = casino.get_user_balance(user_id)

        user_data = casino.data["users"][str(user_id)]
        total_wagered = user_data.get("total_wagered", 0)
        total_won = user_data.get("total_won", 0)

        await update.message.reply_text(
            f"💰 **Vaš balans:** {balance:,} RSD\n\n"
            f"📊 **Statistike:**\n"
            f"🎲 Ukupno uloženo: {total_wagered:,} RSD\n"
            f"🏆 Ukupno dobijeno: {total_won:,} RSD\n"
            f"📈 Neto: {total_won - total_wagered:+,} RSD", 
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in balance_command: {e}")
        await update.message.reply_text("❌ Došlo je do greške. Molimo pokušajte ponovo.")

# Komanda /work
async def work_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Work komanda - daje 30 RSD svakih 3 dana"""
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username or f"User_{user_id}"

        can_work, next_work_time = casino.can_work(user_id)

        if not can_work:
            # Izračunaj koliko vremena je ostalo
            time_left = next_work_time - datetime.now()
            days = time_left.days
            hours, remainder = divmod(time_left.seconds, 3600)
            minutes, _ = divmod(remainder, 60)

            await update.message.reply_text(
                f"⏰ **Već ste radili!**\n\n"
                f"Možete ponovo raditi za:\n"
                f"📅 {days} dana, {hours} sati i {minutes} minuta\n\n"
                f"💼 Povratak rada: {next_work_time.strftime('%d.%m.%Y %H:%M')}",
                parse_mode='Markdown'
            )
            return

        # Dodeli 30 RSD
        work_amount = 30
        old_balance = casino.get_user_balance(user_id)
        new_balance = casino.update_balance(user_id, work_amount)
        casino.set_work_time(user_id)

        # Oduzmi od house balance-a
        casino.data["house_balance"] -= work_amount
        casino.save_data()

        await update.message.reply_text(
            f"💼 **Radni dan završen!**\n\n"
            f"👤 Radnik: {username}\n"
            f"💰 Zaradili ste: +{work_amount} RSD\n"
            f"💳 Novi balans: {new_balance:,} RSD\n\n"
            f"⏰ Sledeći rad za 3 dana!",
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error in work_command: {e}")
        await update.message.reply_text("❌ Došlo je do greške. Molimo pokušajte ponovo.")

# BLACKJACK IGRA SA HOUSE EDGE
class BlackjackGame:
    def __init__(self, user_id: int, bet: int):
        self.user_id = user_id
        self.bet = bet
        self.deck = self.create_deck()
        self.player_hand = []
        self.dealer_hand = []
        self.game_over = False
        self.rigged = casino.is_rigged_game()  # Koristi globalni rigging sistem

    def create_deck(self) -> List[int]:
        """Kreira špil karata (vrednosti)"""
        deck = []
        for _ in range(6):  # 6 špilova
            for _ in range(4):  # 4 karte svake vrednosti
                deck.extend([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10])  # J, Q, K = 10
        random.shuffle(deck)
        return deck

    def deal_card(self) -> int:
        """Deli kartu"""
        if not self.deck:
            self.deck = self.create_deck()
        return self.deck.pop()

    def calculate_hand_value(self, hand: List[int]) -> int:
        """Računa vrednost ruke"""
        value = sum(hand)
        aces = hand.count(1)

        # Računanje asova
        while aces > 0 and value <= 11:
            value += 10  # As kao 11 umesto 1
            aces -= 1

        return value

    def format_cards(self, cards: List[int], hide_first: bool = False) -> str:
        """Formatira karte za prikaz"""
        if hide_first and len(cards) > 0:
            visible_cards = ['?'] + [str(card) for card in cards[1:]]
            return f"[{', '.join(visible_cards)}]"
        return f"[{', '.join(str(card) for card in cards)}]"

    def start_game(self) -> str:
        """Započinje igru"""
        # Deli početne karte
        self.player_hand = [self.deal_card(), self.deal_card()]
        self.dealer_hand = [self.deal_card(), self.deal_card()]

        # Rigging logika za postizanje house edge-a
        if self.rigged:
            # Poboljšaj dealer kartu ako je potrebno
            if self.calculate_hand_value(self.dealer_hand) < 17:
                good_cards = [10, 9,]
                self.dealer_hand[1] = random.choice(good_cards)

        player_value = self.calculate_hand_value(self.player_hand)

        if player_value == 21:
            return self.end_game("blackjack")

        return f"""
🃏 **BLACKJACK** 🃏

💰 Ulog: {self.bet:,} RSD

**Vaše karte:** {self.format_cards(self.player_hand)} (Vrednost: {player_value})
**Dealer karte:** {self.format_cards(self.dealer_hand, hide_first=True)} (Vrednost: ?)

Šta želite da uradite?
        """

    def hit(self) -> str:
        """Igrač uzima kartu"""
        if self.game_over:
            return "Igra je već završena!"

        new_card = self.deal_card()
        self.player_hand.append(new_card)
        player_value = self.calculate_hand_value(self.player_hand)

        if player_value > 21:
            return self.end_game("bust")
        elif player_value == 21:
            return self.end_game("stand")

        return f"""
🃏 **BLACKJACK** 🃏

💰 Ulog: {self.bet:,} RSD

**Vaše karte:** {self.format_cards(self.player_hand)} (Vrednost: {player_value})
**Dealer karte:** {self.format_cards(self.dealer_hand, hide_first=True)} (Vrednost: ?)

Šta želite da uradite?
        """

    def stand(self) -> str:
        """Igrač staje"""
        return self.end_game("stand")

    def end_game(self, action: str) -> str:
        """Završava igru sa house edge kalkulacijom"""
        self.game_over = True
        player_value = self.calculate_hand_value(self.player_hand)

        # Dealer igra
        while self.calculate_hand_value(self.dealer_hand) < 17:
            new_card = self.deal_card()
            self.dealer_hand.append(new_card)

        dealer_value = self.calculate_hand_value(self.dealer_hand)

        # Intenzivniji rigging za postizavanje 7% house edge-a
        if self.rigged and action not in ["bust"]:
            if dealer_value > 21 and random.random() < 0.8:  # 80% šanse da se spase dealer od bust-a
                # Spasi dealer-a od bust-a
                self.dealer_hand[-1] = random.choice([1, 2, 3, 4, 5, 6])
                dealer_value = self.calculate_hand_value(self.dealer_hand)
            elif dealer_value < player_value and dealer_value < 21 and random.random() < 0.7:
                # Poboljšaj dealer ruku
                needed_points = min(21, player_value + 1) - dealer_value
                if needed_points <= 10:
                    self.dealer_hand[-1] = min(10, needed_points)
                    dealer_value = self.calculate_hand_value(self.dealer_hand)

        # Određivanje pobednika
        payout = 0
        result = ""

        if action == "bust":
            result = "🔴 BUST! Prekoračili ste 21."
            payout = -self.bet
        elif action == "blackjack":
            if dealer_value == 21:
                result = "🟡 NERESENO! I vi i dealer imate 21."
                payout = 0
            else:
                result = "🟢 BLACKJACK! Pobedili ste!"
                payout = int(self.bet * 1.5)
        else:
            if dealer_value > 21:
                result = "🟢 POBEDA! Dealer je prekoračio 21."
                payout = self.bet
            elif player_value > dealer_value:
                result = "🟢 POBEDA! Vaša ruka je bolja!"
                payout = self.bet
            elif player_value < dealer_value:
                result = "🔴 PORAZ! Dealer ima bolju ruku."
                payout = -self.bet
            else:
                result = "🟡 NERESENO!"
                payout = 0

        # Ažuriranje balansa i statistika
        new_balance = casino.update_balance(self.user_id, payout)
        casino.update_wager(self.user_id, self.bet)
        casino.update_stats("blackjack", -payout)

        # Logovanje rezultata
        casino.log_game_result(
            self.user_id, 
            "Blackjack", 
            self.bet, 
            result, 
            payout, 
            self.rigged
        )

        return f"""
🃏 **BLACKJACK - REZULTAT** 🃏

**Vaše karte:** {self.format_cards(self.player_hand)} (Vrednost: {player_value})
**Dealer karte:** {self.format_cards(self.dealer_hand)} (Vrednost: {dealer_value})

{result}

💰 Promena balansa: {payout:+,} RSD
💳 Novi balans: {new_balance:,} RSD
        """

# Dictionary za čuvanje aktivnih blackjack igara
active_blackjack_games: Dict[int, BlackjackGame] = {}

# Komanda /play za blackjack
async def play_blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Započinje Blackjack igru"""
    try:
        user_id = update.effective_user.id

        if not context.args:
            await update.message.reply_text(
                "❌ Molimo unesite ulog!\nPrimer: /play 1000"
            )
            return

        try:
            bet = int(context.args[0])
            if bet <= 0:
                await update.message.reply_text("❌ Ulog mora biti pozitivan broj!")
                return
            if bet < 10:
                await update.message.reply_text("❌ Minimalni ulog je 10 RSD!")
                return
        except ValueError:
            await update.message.reply_text("❌ Ulog mora biti broj!")
            return

        balance = casino.get_user_balance(user_id)
        if bet > balance:
            await update.message.reply_text(
                f"❌ Nemate dovoljno sredstava!\n💰 Vaš balans: {balance:,} RSD"
            )
            return

        # Kreiranje nove igre
        game = BlackjackGame(user_id, bet)
        active_blackjack_games[user_id] = game

        game_text = game.start_game()

        if not game.game_over:
            # Kreiranje dugmića
            keyboard = [
                [
                    InlineKeyboardButton("🃏 Hit", callback_data=f"bj_hit_{user_id}"),
                    InlineKeyboardButton("🛑 Stand", callback_data=f"bj_stand_{user_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(game_text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(game_text)
            if user_id in active_blackjack_games:
                del active_blackjack_games[user_id]
    except Exception as e:
        logger.error(f"Error in play_blackjack: {e}")
        await update.message.reply_text("❌ Došlo je do greške. Molimo pokušajte ponovo.")

# Callback handler za blackjack dugmiće
async def blackjack_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Rukuje blackjack dugmićima"""
    try:
        query = update.callback_query
        await query.answer()

        data = query.data.split("_")
        if len(data) < 3:
            await query.edit_message_text("❌ Neispravna komanda!")
            return

        action = data[1]  # hit ili stand
        user_id = int(data[2])

        # Provera da li je korisnik vlasnik igre
        if query.from_user.id != user_id:
            await query.edit_message_text("❌ Ova igra ne pripada vama!")
            return

        if user_id not in active_blackjack_games:
            await query.edit_message_text("❌ Igra nije pronađena!")
            return

        game = active_blackjack_games[user_id]

        if action == "hit":
            result_text = game.hit()
        else:  # stand
            result_text = game.stand()

        if game.game_over:
            await query.edit_message_text(result_text)
            del active_blackjack_games[user_id]
        else:
            keyboard = [
                [
                    InlineKeyboardButton("🃏 Hit", callback_data=f"bj_hit_{user_id}"),
                    InlineKeyboardButton("🛑 Stand", callback_data=f"bj_stand_{user_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(result_text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in blackjack_callback: {e}")
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Došlo je do greške.")

# ROULETTE IGRA SA HOUSE EDGE
async def roulette_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Rulet igra"""
    try:
        user_id = update.effective_user.id

        if not context.args:
            await update.message.reply_text(
                """❌ Molimo unesite ulog!
Primer: /roulette 1000

**Dostupne opcije:**
• red/crveno - black/crno
• even/par - odd/nepar  
• 1-18 - 19-36
• 1-12 - 13-24 - 25-36

Minimalni ulog: 10 RSD"""
            )
            return

        try:
            bet = int(context.args[0])
            if bet <= 0:
                await update.message.reply_text("❌ Ulog mora biti pozitivan broj!")
                return
            if bet < 10:
                await update.message.reply_text("❌ Minimalni ulog je 10 RSD!")
                return
        except ValueError:
            await update.message.reply_text("❌ Ulog mora biti broj!")
            return

        balance = casino.get_user_balance(user_id)
        if bet > balance:
            await update.message.reply_text(
                f"❌ Nemate dovoljno sredstava!\n💰 Vaš balans: {balance:,} RSD"
            )
            return

        # Kreiranje dugmića za opcije
        keyboard = [
            [
                InlineKeyboardButton("🔴 Crveno", callback_data=f"roulette_{user_id}_{bet}_red"),
                InlineKeyboardButton("⚫ Crno", callback_data=f"roulette_{user_id}_{bet}_black")
            ],
            [
                InlineKeyboardButton("📶 Par", callback_data=f"roulette_{user_id}_{bet}_even"),
                InlineKeyboardButton("📈 Nepar", callback_data=f"roulette_{user_id}_{bet}_odd")
            ],
            [
                InlineKeyboardButton("1️⃣-1️⃣8️⃣", callback_data=f"roulette_{user_id}_{bet}_1-18"),
                InlineKeyboardButton("1️⃣9️⃣-3️⃣6️⃣", callback_data=f"roulette_{user_id}_{bet}_19-36")
            ],
            [
                InlineKeyboardButton("1️⃣-1️⃣2️⃣", callback_data=f"roulette_{user_id}_{bet}_1-12"),
                InlineKeyboardButton("1️⃣3️⃣-2️⃣4️⃣", callback_data=f"roulette_{user_id}_{bet}_13-24"),
                InlineKeyboardButton("2️⃣5️⃣-3️⃣6️⃣", callback_data=f"roulette_{user_id}_{bet}_25-36")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"🎰 **RULET** 🎰\n\n💰 Ulog: {bet:,} RSD\n\nIzaberite vašu opciju:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in roulette_game: {e}")
        await update.message.reply_text("❌ Došlo je do greške. Molimo pokušajte ponovo.")

async def roulette_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Rukuje rulet opcijama sa house edge"""
    try:
        query = update.callback_query
        await query.answer()

        data = query.data.split("_")
        if len(data) < 4:
            await query.edit_message_text("❌ Neispravna komanda!")
            return

        user_id = int(data[1])
        bet = int(data[2])
        choice = data[3]

        if query.from_user.id != user_id:
            await query.edit_message_text("❌ Ova opklada ne pripada vama!")
            return

        # Globalni rigging sistem za house edge
        rigged = casino.is_rigged_game()

        # Generisanje broja sa house edge logikom
        if rigged:
            # Intenzivniji rigging za roulette (jer ima veći house edge prirodno)
            losing_numbers = []

            if choice == "red":
                losing_numbers = [0] + [i for i in range(1, 37) if i not in [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]]
            elif choice == "black":
                losing_numbers = [0] + [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
            elif choice == "even":
                losing_numbers = [0] + list(range(1, 37, 2))  # Neparni brojevi + 0
            elif choice == "odd":
                losing_numbers = [0] + list(range(2, 37, 2))  # Parni brojevi + 0
            elif choice == "1-18":
                losing_numbers = [0] + list(range(19, 37))
            elif choice == "19-36":
                losing_numbers = [0] + list(range(1, 19))
            elif choice == "1-12":
                losing_numbers = [0] + list(range(13, 37))
            elif choice == "13-24":
                losing_numbers = [0] + list(range(1, 13)) + list(range(25, 37))
            elif choice == "25-36":
                losing_numbers = [0] + list(range(1, 25))

            if losing_numbers and random.random() < 0.85:  # 85% šanse da se izabere losing broj
                number = random.choice(losing_numbers)
            else:
                number = random.randint(0, 36)
        else:
            number = random.randint(0, 36)

        # Animacija
        await query.edit_message_text("🎰 Rulet se okreće... 🎰")
        await asyncio.sleep(1)
        await query.edit_message_text("🎰 Rulet se okreće... 🌀")
        await asyncio.sleep(1)
        await query.edit_message_text("🎰 Rulet se zadržava... ⏱️")
        await asyncio.sleep(1)

        # Određivanje boje
        red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
        color = "🔴" if number in red_numbers else "⚫" if number != 0 else "🟢"

        # Provera da li je igrač pobedio
        won = False
        payout = 0
        multiplier = 0

        if choice == "red" and number in red_numbers:
            won = True
            multiplier = 2
        elif choice == "black" and number not in red_numbers and number != 0:
            won = True
            multiplier = 2
        elif choice == "even" and number > 0 and number % 2 == 0:
            won = True
            multiplier = 2
        elif choice == "odd" and number % 2 == 1:
            won = True
            multiplier = 2
        elif choice == "1-18" and 1 <= number <= 18:
            won = True
            multiplier = 2
        elif choice == "19-36" and 19 <= number <= 36:
            won = True
            multiplier = 2
        elif choice == "1-12" and 1 <= number <= 12:
            won = True
            multiplier = 3
        elif choice == "13-24" and 13 <= number <= 24:
            won = True
            multiplier = 3
        elif choice == "25-36" and 25 <= number <= 36:
            won = True
            multiplier = 3

        if won:
            payout = bet * (multiplier - 1)
            result_text = "🟢 POBEDA!"
        else:
            payout = -bet
            result_text = "🔴 PORAZ!"

        # Ažuriranje balansa i statistika
        new_balance = casino.update_balance(user_id, payout)
        casino.update_wager(user_id, bet)
        casino.update_stats("roulette", -payout)

        # Logovanje rezultata
        casino.log_game_result(user_id, "Roulette", bet, f"{result_text} Broj: {number}", payout, rigged)

        choice_text = {
            "red": "Crveno", "black": "Crno", "even": "Par", "odd": "Nepar",
            "1-18": "1-18", "19-36": "19-36", "1-12": "1-12", 
            "13-24": "13-24", "25-36": "25-36"
        }.get(choice, choice)

        final_text = f"""
🎰 **RULET - REZULTAT** 🎰

{color} **Broj:** {number}

**Vaš izbor:** {choice_text}
{result_text}

💰 Promena balansa: {payout:+,} RSD
💳 Novi balans: {new_balance:,} RSD
        """

        await query.edit_message_text(final_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in roulette_callback: {e}")
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Došlo je do greške.")

# DICE IGRA SA HOUSE EDGE
async def dice_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dice igra sa house edge"""
    try:
        user_id = update.effective_user.id

        if len(context.args) < 2:
            await update.message.reply_text(
                """❌ Molimo unesite ulog i brojeve!
Primer: /dice 1000 1 3 6

**Pravila:**
• Možete birati 1-3 broja (od 1 do 6)
• Isplata: 1 broj = 5.5x, 2 broja = 2.8x, 3 broja = 1.8x
• Minimalni ulog: 10 RSD"""
            )
            return

        try:
            bet = int(context.args[0])
            if bet <= 0:
                await update.message.reply_text("❌ Ulog mora biti pozitivan broj!")
                return
            if bet < 10:
                await update.message.reply_text("❌ Minimalni ulog je 10 RSD!")
                return
        except ValueError:
            await update.message.reply_text("❌ Ulog mora biti broj!")
            return

        # Parsiranje brojeva
        try:
            chosen_numbers = [int(x) for x in context.args[1:]]
            if len(chosen_numbers) > 3:
                await update.message.reply_text("❌ Možete birati maksimalno 3 broja!")
                return
            if any(n < 1 or n > 6 for n in chosen_numbers):
                await update.message.reply_text("❌ Brojevi moraju biti između 1 i 6!")
                return
            if len(set(chosen_numbers)) != len(chosen_numbers):
                await update.message.reply_text("❌ Ne možete birati isti broj više puta!")
                return
        except ValueError:
            await update.message.reply_text("❌ Brojevi moraju biti validni!")
            return

        balance = casino.get_user_balance(user_id)
        if bet > balance:
            await update.message.reply_text(
                f"❌ Nemate dovoljno sredstava!\n💰 Vaš balans: {balance:,} RSD"
            )
            return

        # Globalni rigging sistem
        rigged = casino.is_rigged_game()

        if rigged:
            # Pokušaj da se izabere broj koji nije u chosen_numbers
            possible_numbers = [i for i in range(1, 7) if i not in chosen_numbers]
            if possible_numbers and random.random() < 0.9:  # 90% šanse da se izabere losing broj
                dice_result = random.choice(possible_numbers)
            else:
                dice_result = random.randint(1, 6)
        else:
            dice_result = random.randint(1, 6)

        # Animacija
        message = await update.message.reply_text("🎲 Bacanje kockice... 🎲")
        await asyncio.sleep(1)
        await message.edit_text("🎲 Kockica se kotrlja... 🔄")
        await asyncio.sleep(1)
        await message.edit_text("🎲 Kockica se zaustavlja... ⏳")
        await asyncio.sleep(1)

        # Provera pobede
        won = dice_result in chosen_numbers

        if won:
            # Multipliers sa house edge-om (smanjeni)
            multipliers = {1: 5.5, 2: 2.8, 3: 1.8}
            multiplier = multipliers[len(chosen_numbers)]
            payout = int(bet * (multiplier - 1))
            result_text = "🟢 POBEDA!"
        else:
            payout = -bet
            result_text = "🔴 PORAZ!"

        # Ažuriranje balansa i statistika
        new_balance = casino.update_balance(user_id, payout)
        casino.update_wager(user_id, bet)
        casino.update_stats("dice", -payout)

        # Logovanje rezultata
        casino.log_game_result(user_id, "Dice", bet, f"{result_text} Rezultat: {dice_result}", payout, rigged)

        final_text = f"""
🎲 **DICE - REZULTAT** 🎲

🎯 **Rezultat:** {dice_result}

**Vaši brojevi:** {', '.join(map(str, chosen_numbers))}
{result_text}

💰 Promena balansa: {payout:+,} RSD
💳 Novi balans: {new_balance:,} RSD
        """

        await message.edit_text(final_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in dice_game: {e}")
        await update.message.reply_text("❌ Došlo je do greške. Molimo pokušajte ponovo.")

# COINFLIP IGRA SA HOUSE EDGE
async def coinflip_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Coinflip igra sa house edge"""
    try:
        user_id = update.effective_user.id

        if len(context.args) != 2:
            await update.message.reply_text(
                """❌ Molimo unesite ulog i izbor!
Primer: /flip 1000 heads
ili: /flip 1000 tails

**Opcije:** heads/tails
**Isplata:** 1.86x (umesto 2x)
**Minimalni ulog:** 10 RSD"""
            )
            return

        try:
            bet = int(context.args[0])
            if bet <= 0:
                await update.message.reply_text("❌ Ulog mora biti pozitivan broj!")
                return
            if bet < 10:
                await update.message.reply_text("❌ Minimalni ulog je 10 RSD!")
                return
        except ValueError:
            await update.message.reply_text("❌ Ulog mora biti broj!")
            return

        choice = context.args[1].lower()
        if choice not in ['heads', 'tails']:
            await update.message.reply_text("❌ Izbor mora biti 'heads' ili 'tails'!")
            return

        balance = casino.get_user_balance(user_id)
        if bet > balance:
            await update.message.reply_text(
                f"❌ Nemate dovoljno sredstava!\n💰 Vaš balans: {balance:,} RSD"
            )
            return

        # Globalni rigging sistem
        rigged = casino.is_rigged_game()

        if rigged:
            # 80% šanse da rezultat bude suprotan od izbora
            if random.random() < 0.8:
                result = 'tails' if choice == 'heads' else 'heads'
            else:
                result = random.choice(['heads', 'tails'])
        else:
            result = random.choice(['heads', 'tails'])

        # Animacija
        message = await update.message.reply_text("🪙 Bacanje novčića... 🪙")
        await asyncio.sleep(1)
        await message.edit_text("🪙 Novčić se okreće... 🔄")
        await asyncio.sleep(1)
        await message.edit_text("🪙 Novčić pada... ⬇️")
        await asyncio.sleep(1)

        # Provera pobede
        won = choice == result

        if won:
            # Smanjen multiplier za house edge (1.86x umesto 2x)
            payout = int(bet * 0.86)
            result_text = "🟢 POBEDA!"
        else:
            payout = -bet
            result_text = "🔴 PORAZ!"

        # Ažuriranje balansa i statistika
        new_balance = casino.update_balance(user_id, payout)
        casino.update_wager(user_id, bet)
        casino.update_stats("coinflip", -payout)

        # Logovanje rezultata
        casino.log_game_result(user_id, "Coinflip", bet, f"{result_text} Rezultat: {result}", payout, rigged)

        result_emoji = "🟡" if result == "heads" else "⚪"
        choice_emoji = "🟡" if choice == "heads" else "⚪"

        final_text = f"""
🪙 **COINFLIP - REZULTAT** 🪙

{result_emoji} **Rezultat:** {result.upper()}

{choice_emoji} **Vaš izbor:** {choice.upper()}
{result_text}

💰 Promena balansa: {payout:+,} RSD
💳 Novi balans: {new_balance:,} RSD
        """

        await message.edit_text(final_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in coinflip_game: {e}")
        await update.message.reply_text("❌ Došlo je do greške. Molimo pokušajte ponovo.")

# BROADCAST SISTEM
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin komanda za broadcast poruku svim korisnicima"""
    try:
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Nemate dozvolu za ovu komandu!")
            return

        if not context.args:
            await update.message.reply_text(
                "❌ Molimo unesite poruku za broadcast!\n"
                "Primer: /broadcast Dobrodošli u novi Casino Bot!"
            )
            return

        message_text = " ".join(context.args)
        all_users = casino.get_all_users()

        if not all_users:
            await update.message.reply_text("❌ Nema korisnika za broadcast!")
            return

        # Pošaljemo poruku svim korisnicima
        success_count = 0
        failed_count = 0

        status_message = await update.message.reply_text(
            f"📡 **BROADCAST POKRENUO**\n\n"
            f"👥 Ukupno korisnika: {len(all_users)}\n"
            f"✅ Poslato: 0\n"
            f"❌ Neuspešno: 0",
            parse_mode='Markdown'
        )

        for i, user_id in enumerate(all_users):
            try:
                await context.bot.send_message(
                    user_id,
                    f"📢 **OBAVEŠTENJE**\n\n{message_text}",
                    parse_mode='Markdown'
                )
                success_count += 1

                # Ažuriraj status svakih 10 poruka
                if (i + 1) % 10 == 0:
                    await status_message.edit_text(
                        f"📡 **BROADCAST U TOKU**\n\n"
                        f"👥 Ukupno korisnika: {len(all_users)}\n"
                        f"✅ Poslato: {success_count}\n"
                        f"❌ Neuspešno: {failed_count}\n"
                        f"⏳ Obrađeno: {i + 1}/{len(all_users)}",
                        parse_mode='Markdown'
                    )

                # Kratka pauza između poruka
                await asyncio.sleep(0.05)

            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to send broadcast to {user_id}: {e}")

        # Finalni status
        await status_message.edit_text(
            f"📡 **BROADCAST ZAVRŠEN**\n\n"
            f"👥 Ukupno korisnika: {len(all_users)}\n"
            f"✅ Uspešno poslato: {success_count}\n"
            f"❌ Neuspešno: {failed_count}\n\n"
            f"📝 Poruka: {message_text[:100]}{'...' if len(message_text) > 100 else ''}",
            parse_mode='Markdown'
        )

        # Sačuvaj broadcast u istoriju
        casino.data["broadcast_history"].append({
            "timestamp": datetime.now().isoformat(),
            "message": message_text,
            "total_users": len(all_users),
            "success_count": success_count,
            "failed_count": failed_count
        })

        # Čuvaj samo poslednih 50 broadcast-ova
        if len(casino.data["broadcast_history"]) > 50:
            casino.data["broadcast_history"] = casino.data["broadcast_history"][-50:]

        casino.save_data()

    except Exception as e:
        logger.error(f"Error in broadcast_command: {e}")
        await update.message.reply_text("❌ Došlo je do greške tokom broadcast-a.")

# ADMIN KOMANDE
async def add_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin komanda za dodavanje balansa"""
    try:
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Nemate dozvolu za ovu komandu!")
            return

        if len(context.args) != 2:
            await update.message.reply_text("❌ Korišćenje: /add <user_id> <iznos>")
            return

        try:
            target_user_id = int(context.args[0])
            amount = int(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ User ID i iznos moraju biti brojevi!")
            return

        # Dodaj balans korisniku
        old_balance = casino.get_user_balance(target_user_id)
        new_balance = casino.update_balance(target_user_id, amount)

        # Ažuriraj house balance
        casino.data["house_balance"] -= amount
        casino.save_data()

        await update.message.reply_text(
            f"✅ **Balans je ažuriran!**\n\n"
            f"👤 Korisnik: {target_user_id}\n"
            f"💰 Stari balans: {old_balance:,} RSD\n"
            f"➕ Dodano: {amount:+,} RSD\n"
            f"💳 Novi balans: {new_balance:,} RSD",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in add_balance_command: {e}")
        await update.message.reply_text("❌ Došlo je do greške. Molimo pokušajte ponovo.")

async def remove_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin komanda za oduzimanje balansa"""
    try:
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Nemate dozvolu za ovu komandu!")
            return

        if len(context.args) != 2:
            await update.message.reply_text("❌ Korišćenje: /remove <user_id> <iznos>")
            return

        try:
            target_user_id = int(context.args[0])
            amount = int(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ User ID i iznos moraju biti brojevi!")
            return

        # Oduzmi balans korisniku
        old_balance = casino.get_user_balance(target_user_id)
        new_balance = casino.update_balance(target_user_id, -amount)

        # Ažuriraj house balance
        casino.data["house_balance"] += amount
        casino.save_data()

        await update.message.reply_text(
            f"✅ **Balans je ažuriran!**\n\n"
            f"👤 Korisnik: {target_user_id}\n"
            f"💰 Stari balans: {old_balance:,} RSD\n"
            f"➖ Oduzeto: {amount:,} RSD\n"
            f"💳 Novi balans: {new_balance:,} RSD",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in remove_balance_command: {e}")
        await update.message.reply_text("❌ Došlo je do greške. Molimo pokušajte ponovo.")

async def house_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin komanda za prikaz house balansa i statistika"""
    try:
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Nemate dozvolu za ovu komandu!")
            return

        house_balance = casino.data.get("house_balance", 0)
        total_users = len(casino.data.get("users", {}))
        total_user_balance = sum(user.get("balance", 0) for user in casino.data.get("users", {}).values())

        # Statistike igara
        stats = casino.data.get("stats", {})
        total_games = sum(game_stat.get("games", 0) for game_stat in stats.values())
        total_house_profit = sum(game_stat.get("profit", 0) for game_stat in stats.values())

        # Statistike rigging-a iz poslednje igre
        recent_games = casino.data.get("game_history", [])[-50:]
        rigged_count = sum(1 for game in recent_games if game.get("rigged", False))

        # House edge izračun
        total_wagered = sum(user.get("total_wagered", 0) for user in casino.data.get("users", {}).values())
        actual_house_edge = (total_house_profit / total_wagered * 100) if total_wagered > 0 else 0

        stats_text = "\n".join([
            f"🎲 {game.title()}: {data.get('games', 0)} igara, {data.get('profit', 0):+,} RSD"
            for game, data in stats.items()
        ])

        await update.message.reply_text(
            f"🏦 **HOUSE STATUS**\n\n"
            f"💰 House Balance: {house_balance:,} RSD\n"
            f"👥 Ukupno korisnika: {total_users}\n"
            f"💳 Balans korisnika: {total_user_balance:,} RSD\n\n"
            f"📊 **Statistike igara:**\n"
            f"{stats_text}\n\n"
            f"🎯 **House Edge:**\n"
            f"📈 Cilj: 7.00%\n"
            f"📊 Stvarni: {actual_house_edge:.2f}%\n"
            f"💸 Ukupan profit: {total_house_profit:,} RSD\n\n"
            f"🎰 **Rigging statistike:**\n"
            f"⚙️ Poslednje 50 igara: {rigged_count}/50 rigged\n"
            f"📋 Ukupno igara: {total_games}",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in house_balance_command: {e}")
        await update.message.reply_text("❌ Došlo je do greške. Molimo pokušajte ponovo.")

# CASHOUT SISTEM
async def cashout_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Komanda za zahtev za cashout"""
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username or f"User_{user_id}"

        if not context.args:
            await update.message.reply_text(
                "❌ Molimo unesite iznos!\n"
                "Primer: /cashout 5000\n"
                "Minimalni cashout: 1,000 RSD"
            )
            return

        try:
            amount = int(context.args[0])
            if amount <= 0:
                await update.message.reply_text("❌ Iznos mora biti pozitivan broj!")
                return
        except ValueError:
            await update.message.reply_text("❌ Iznos mora biti broj!")
            return

        balance = casino.get_user_balance(user_id)
        if amount > balance:
            await update.message.reply_text(
                f"❌ Nemate dovoljno sredstava!\n💰 Vaš balans: {balance:,} RSD"
            )
            return

        if amount < 1000:
            await update.message.reply_text("❌ Minimalni cashout je 1.000 RSD!")
            return

        # Ensure cashout_requests exists
        casino._ensure_data_structure(casino.data)

        # Kreiranje zahteva za cashout
        request_id = f"cashout_{user_id}_{int(datetime.now().timestamp())}"
        casino.data["cashout_requests"][request_id] = {
            "user_id": user_id,
            "username": username,
            "amount": amount,
            "timestamp": datetime.now().isoformat(),
            "status": "pending"
        }

        # Rezerviši sredstva (oduzmi iz balansa)
        casino.update_balance(user_id, -amount)

        casino.save_data()

        # Obavesti admina
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"💸 **NOVI CASHOUT ZAHTEV**\n\n"
                f"👤 Korisnik: @{username} (ID: {user_id})\n"
                f"💰 Iznos: {amount:,} RSD\n"
                f"🆔 Request ID: {request_id}\n\n"
                f"Koristite /cashouts za upravljanje zahtevima.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to notify admin about cashout: {e}")

        await update.message.reply_text(
            f"✅ **Cashout zahtev je poslat!**\n\n"
            f"💰 Iznos: {amount:,} RSD\n"
            f"🆔 Request ID: {request_id}\n\n"
            f"Sredstva su rezervisana i biće isplaćena nakon odobravanja.\n"
            f"Dobićete kod za preuzimanje kada admin odobri zahtev.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in cashout_command: {e}")
        await update.message.reply_text("❌ Došlo je do greške. Molimo pokušajte ponovo.")

async def cashouts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin komanda za upravljanje cashout zahtevima"""
    try:
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Nemate dozvolu za ovu komandu!")
            return

        # Ensure cashout_requests exists
        casino._ensure_data_structure(casino.data)

        pending_requests = {k: v for k, v in casino.data["cashout_requests"].items() 
                           if v.get("status") == "pending"}

        if not pending_requests:
            await update.message.reply_text("📭 Nema pending cashout zahteva.")
            return

        # Kreiranje dugmića za svaki zahtev
        keyboard = []
        for request_id, request_data in list(pending_requests.items())[:10]:  # Maksimalno 10 zahteva
            username = request_data.get("username", "Unknown")
            amount = request_data.get("amount", 0)
            button_text = f"✅ {username}: {amount:,} RSD"
            keyboard.append([
                InlineKeyboardButton(button_text, callback_data=f"approve_cashout_{request_id}")
            ])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "💸 **PENDING CASHOUT ZAHTEVI**\n\nKliknite na zahtev da ga odobrite:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in cashouts_command: {e}")
        await update.message.reply_text("❌ Došlo je do greške. Molimo pokušajte ponovo.")

async def approve_cashout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Odobrava cashout zahtev"""
    try:
        query = update.callback_query
        await query.answer()

        if query.from_user.id != ADMIN_ID:
            await query.edit_message_text("❌ Nemate dozvolu!")
            return

        request_id = query.data.replace("approve_cashout_", "")

        if request_id not in casino.data.get("cashout_requests", {}):
            await query.edit_message_text("❌ Zahtev nije pronađen!")
            return

        request_data = casino.data["cashout_requests"][request_id]
        if request_data.get("status") != "pending":
            await query.edit_message_text("❌ Zahtev je već obrađen!")
            return

        # Generiši kod
        cashout_code = f"CASH{random.randint(10000, 99999)}"

        # Ažuriraj zahtev
        casino.data["cashout_requests"][request_id]["status"] = "approved"
        casino.data["cashout_requests"][request_id]["code"] = cashout_code
        casino.data["cashout_requests"][request_id]["approved_at"] = datetime.now().isoformat()

        casino.save_data()

        # Pošalji kod korisniku
        try:
            await context.bot.send_message(
                request_data["user_id"],
                f"✅ **CASHOUT ODOBREN!**\n\n"
                f"💰 Iznos: {request_data['amount']:,} RSD\n"
                f"🔐 Kod: **{cashout_code}**\n\n"
                f"Kontaktirajte support sa ovim kodom za preuzimanje sredstava.",
                parse_mode='Markdown'
            )

            await query.edit_message_text(
                f"✅ **Cashout odobren!**\n\n"
                f"👤 Korisnik: {request_data.get('username', 'Unknown')}\n"
                f"💰 Iznos: {request_data.get('amount', 0):,} RSD\n"
                f"🔐 Kod poslat korisniku: {cashout_code}",
                parse_mode='Markdown'
            )

        except Exception as e:
            await query.edit_message_text(f"❌ Greška pri slanju koda: {str(e)}")
    except Exception as e:
        logger.error(f"Error in approve_cashout_callback: {e}")
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Došlo je do greške.")

# GLAVNI CALLBACK HANDLER
async def main_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Glavni callback handler za sve dugmiće"""
    try:
        query = update.callback_query

        if not query or not query.data:
            return

        if query.data.startswith("bj_"):
            await blackjack_callback(update, context)
        elif query.data.startswith("roulette_"):
            await roulette_callback(update, context)
        elif query.data.startswith("approve_cashout_"):
            await approve_cashout_callback(update, context)
        else:
            await query.answer("❌ Nepoznata komanda!")
    except Exception as e:
        logger.error(f"Error in main_callback_handler: {e}")
        if update.callback_query:
            await update.callback_query.answer("❌ Došlo je do greške.")

# HELP KOMANDA
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Help komanda sa svim dostupnim komandama"""
    try:
        user_id = update.effective_user.id

        help_text = f"""
🎰 **CASINO BOT - KOMANDE** 🎰

**🎮 Igre (House Edge: 7%):**
🃏 /play <ulog> - Blackjack
🎰 /roulette <ulog> - Rulet (zatim izaberi opciju)
🎲 /dice <ulog> <brojevi> - Dice (1-3 broja od 1-6)
🪙 /flip <ulog> <heads/tails> - Coinflip

**💰 Balans:**
💳 /bal - Proveri balans i statistike
💼 /work - Radi za 30 RSD (svaka 3 dana)
💸 /cashout <iznos> - Zatraži isplatu (min. 1,000 RSD)

**ℹ️ Ostalo:**
🏠 /start - Početna poruka
❓ /help - Ova poruka

**📏 Minimalni ulog:** 10 RSD na sve igre
        """

        # Admin komande (samo za admina)
        if user_id == ADMIN_ID:
            help_text += """
**🔧 Admin komande:**
➕ /add <user_id> <iznos> - Dodaj balans
➖ /remove <user_id> <iznos> - Oduzmi balans  
🏦 /house - House balans i detaljne statistike
💸 /cashouts - Upravljanje cashout zahtevima
📡 /broadcast <poruka> - Pošalji poruku svim korisnicima
            """

        help_text += f"""
"""

        await update.message.reply_text(help_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in help_command: {e}")
        await update.message.reply_text("❌ Došlo je do greške. Molimo pokušajte ponovo.")

# BROADCAST MESSAGE HANDLER (za odgovor na broadcast)
async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Rukuje porukama koje nisu komande (za broadcast odgovor)"""
    try:
        # Ova funkcija se pozove samo ako poruka nije komanda
        # Možemo je koristiti za logovanje ili druge funkcionalnosti
        pass
    except Exception as e:
        logger.error(f"Error in handle_broadcast_message: {e}")

# ERROR HANDLER
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Rukuje greškama"""
    logger.error(f"Update {update} caused error {context.error}")

    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Došlo je do greške. Molimo pokušajte ponovo."
            )
    except Exception as e:
        logger.error(f"Error in error_handler: {e}")

def main():
    """Glavna funkcija za pokretanje bota"""
    try:
        # Kreiranje aplikacije
        application = Application.builder().token(BOT_TOKEN).build()

        # Registracija komandi
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("bal", balance_command))
        application.add_handler(CommandHandler("work", work_command))

        # Igre
        application.add_handler(CommandHandler("play", play_blackjack))
        application.add_handler(CommandHandler("roulette", roulette_game))
        application.add_handler(CommandHandler("dice", dice_game))
        application.add_handler(CommandHandler("flip", coinflip_game))

        # Admin komande
        application.add_handler(CommandHandler("add", add_balance_command))
        application.add_handler(CommandHandler("remove", remove_balance_command))
        application.add_handler(CommandHandler("house", house_balance_command))
        application.add_handler(CommandHandler("broadcast", broadcast_command))

        # Cashout sistem
        application.add_handler(CommandHandler("cashout", cashout_command))
        application.add_handler(CommandHandler("cashouts", cashouts_command))

        # Callback handlers
        application.add_handler(CallbackQueryHandler(main_callback_handler))

        # Message handler za sve ostale poruke (ne-komande)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast_message))

        # Error handler
        application.add_error_handler(error_handler)

        # Pokretanje bota
        print("🎰 Casino bot je pokrenuo sa novim funkcionalnostima!")
        print(f"📁 Podaci se čuvaju u: {DATA_FILE}")
        print(f"🔧 Admin ID: {ADMIN_ID}")
        print(f"📊 House Edge: {HOUSE_EDGE*100}%")
        print(f"⚙️ Rigging Probability: {RIGGING_PROBABILITY*100}%")
        print("💼 Work funkcija: 30 RSD svakih 3 dana")
        print("📡 Broadcast sistem je aktivan")

        application.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        print(f"❌ Greška pri pokretanju bota: {e}")

if __name__ == '__main__':
    main()
