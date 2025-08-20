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
HOUSE_EDGE = 0.1  # 10% house edge
RIGGING_PROBABILITY = 0.37  # 37% šanse za rigging

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
                self._ensure_data_structure(data)
                return data
        except FileNotFoundError:
            logger.info("Data file not found, creating new one")
            return self._create_default_data()
        except json.JSONDecodeError:
            logger.error("JSON file is corrupted, creating new one")
            return self._create_default_data()
        except Exception as e:
            logger.error(f"Error loading data: {e}")
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
            "work_cooldowns": {},
            "promo_codes": {},
            "promo_usage": {}
        }
        self.save_data(default_data)
        return default_data

    def _ensure_data_structure(self, data: Dict[str, Any]) -> None:
        """Osigurava da postoje svi potrebni ključevi u podatkovnoj strukturi"""
        try:
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
            if "promo_codes" not in data:
                data["promo_codes"] = {}
            if "promo_usage" not in data:
                data["promo_usage"] = {}
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
                if not isinstance(user_data, dict):
                    data["users"][user_id] = {"balance": 0, "username": "", "total_wagered": 0, "total_won": 0, "last_work": None, "used_promo_codes": []}
                    continue
                    
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
                if "used_promo_codes" not in user_data:
                    user_data["used_promo_codes"] = []
        except Exception as e:
            logger.error(f"Error ensuring data structure: {e}")

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
        try:
            user_id = str(user_id)
            if user_id not in self.data["users"]:
                self.data["users"][user_id] = {
                    "balance": 0,
                    "username": "",
                    "total_wagered": 0,
                    "total_won": 0,
                    "last_work": None,
                    "used_promo_codes": []
                }
                self.save_data()
            return int(self.data["users"][user_id].get("balance", 0))
        except Exception as e:
            logger.error(f"Error getting user balance: {e}")
            return 0

    def update_balance(self, user_id: int, amount: int) -> int:
        """Ažurira balans korisnika"""
        try:
            user_id = str(user_id)
            if user_id not in self.data["users"]:
                self.get_user_balance(int(user_id))

            current_balance = int(self.data["users"][user_id].get("balance", 0))
            new_balance = current_balance + amount
            self.data["users"][user_id]["balance"] = new_balance

            # Ažuriranje house balance-a
            current_house = int(self.data.get("house_balance", 100000))
            self.data["house_balance"] = current_house - amount

            # Ažuriranje total_won ako je amount pozitivan
            if amount > 0:
                current_won = int(self.data["users"][user_id].get("total_won", 0))
                self.data["users"][user_id]["total_won"] = current_won + amount

            self.save_data()
            return new_balance
        except Exception as e:
            logger.error(f"Error updating balance: {e}")
            return self.get_user_balance(int(user_id))

    def update_wager(self, user_id: int, amount: int) -> None:
        """Ažurira ukupan iznos opklada"""
        try:
            user_id = str(user_id)
            if user_id not in self.data["users"]:
                self.get_user_balance(int(user_id))

            current_wagered = int(self.data["users"][user_id].get("total_wagered", 0))
            self.data["users"][user_id]["total_wagered"] = current_wagered + amount
            self.save_data()
        except Exception as e:
            logger.error(f"Error updating wager: {e}")

    def update_stats(self, game: str, profit: int) -> None:
        """Ažurira statistike igre"""
        try:
            self._ensure_data_structure(self.data)

            if game in self.data["stats"]:
                current_games = int(self.data["stats"][game].get("games", 0))
                current_profit = int(self.data["stats"][game].get("profit", 0))
                
                self.data["stats"][game]["games"] = current_games + 1
                self.data["stats"][game]["profit"] = current_profit + profit
                self.save_data()
        except Exception as e:
            logger.error(f"Error updating stats: {e}")

    def log_game_result(self, user_id: int, game: str, bet: int, result: str, payout: int, rigged: bool = False) -> None:
        """Loguje rezultat igre"""
        try:
            if "game_history" not in self.data:
                self.data["game_history"] = []
                
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
        try:
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
        except Exception as e:
            logger.error(f"Error checking work availability: {e}")
            return True, None

    def set_work_time(self, user_id: int) -> None:
        """Postavlja vreme poslednjeg rada"""
        try:
            user_id = str(user_id)
            if user_id not in self.data["users"]:
                self.get_user_balance(int(user_id))

            self.data["users"][user_id]["last_work"] = datetime.now().isoformat()
            self.save_data()
        except Exception as e:
            logger.error(f"Error setting work time: {e}")

    def get_all_users(self) -> List[int]:
        """Vraća listu svih user ID-ova"""
        try:
            return [int(user_id) for user_id in self.data.get("users", {}).keys()]
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []

    def is_rigged_game(self) -> bool:
        """Određuje da li je igra rigged na osnovu house edge-a"""
        try:
            return random.random() < RIGGING_PROBABILITY
        except:
            return False

    # PROMO CODE SISTEM
    def create_promo_code(self, code: str, amount: int, max_uses: int, expires_at: Optional[datetime] = None) -> bool:
        """Kreira novi promo kod"""
        try:
            code = code.upper()
            
            if "promo_codes" not in self.data:
                self.data["promo_codes"] = {}
            if "promo_usage" not in self.data:
                self.data["promo_usage"] = {}
            
            if code in self.data["promo_codes"]:
                return False
            
            self.data["promo_codes"][code] = {
                "amount": amount,
                "max_uses": max_uses,
                "current_uses": 0,
                "created_at": datetime.now().isoformat(),
                "expires_at": expires_at.isoformat() if expires_at else None,
                "active": True
            }
            
            self.data["promo_usage"][code] = []
            self.save_data()
            return True
        except Exception as e:
            logger.error(f"Error creating promo code: {e}")
            return False

    def use_promo_code(self, user_id: int, code: str) -> tuple[bool, str, int]:
        """Pokušava da iskoristi promo kod"""
        try:
            user_id = str(user_id)
            code = code.upper()
            
            if user_id not in self.data["users"]:
                self.get_user_balance(int(user_id))
            
            if "promo_codes" not in self.data or code not in self.data["promo_codes"]:
                return False, "❌ Promo kod ne postoji!", 0
            
            promo_data = self.data["promo_codes"][code]
            
            if not promo_data.get("active", True):
                return False, "❌ Promo kod je deaktiviran!", 0
            
            if promo_data.get("expires_at"):
                expiry_date = datetime.fromisoformat(promo_data["expires_at"])
                if datetime.now() > expiry_date:
                    return False, "❌ Promo kod je istekao!", 0
            
            if promo_data["current_uses"] >= promo_data["max_uses"]:
                return False, "❌ Promo kod je dostigao maksimalan broj korišćenja!", 0
            
            user_promo_codes = self.data["users"][user_id].get("used_promo_codes", [])
            if code in user_promo_codes:
                return False, "❌ Već ste iskoristili ovaj promo kod!", 0
            
            amount = promo_data["amount"]
            
            self.update_balance(int(user_id), amount)
            
            if "used_promo_codes" not in self.data["users"][user_id]:
                self.data["users"][user_id]["used_promo_codes"] = []
            self.data["users"][user_id]["used_promo_codes"].append(code)
            
            self.data["promo_codes"][code]["current_uses"] += 1
            
            if "promo_usage" not in self.data:
                self.data["promo_usage"] = {}
            if code not in self.data["promo_usage"]:
                self.data["promo_usage"][code] = []
            
            self.data["promo_usage"][code].append({
                "user_id": int(user_id),
                "username": self.data["users"][user_id].get("username", "Unknown"),
                "timestamp": datetime.now().isoformat()
            })
            
            self.save_data()
            
            return True, f"✅ Promo kod uspešno iskorišćen! Dobili ste {amount:,} RSD!", amount
            
        except Exception as e:
            logger.error(f"Error using promo code: {e}")
            return False, "❌ Došlo je do greške pri korišćenju promo koda!", 0

    def get_promo_code_info(self, code: str) -> Optional[Dict[str, Any]]:
        """Vraća informacije o promo kodu"""
        try:
            code = code.upper()
            if "promo_codes" not in self.data or code not in self.data["promo_codes"]:
                return None
            
            promo_data = self.data["promo_codes"][code].copy()
            promo_data["usage_log"] = self.data.get("promo_usage", {}).get(code, [])
            return promo_data
        except Exception as e:
            logger.error(f"Error getting promo code info: {e}")
            return None

    def get_all_promo_codes(self) -> Dict[str, Any]:
        """Vraća sve promo kodove"""
        try:
            return self.data.get("promo_codes", {}).copy()
        except Exception as e:
            logger.error(f"Error getting all promo codes: {e}")
            return {}

# Kreiranje instance bota
casino = CasinoBot()

# KOMANDE
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start komanda sa pozdravom i prikazom balansa"""
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username or "Nepoznat"

        # Čuvanje username-a
        user_id_str = str(user_id)
        if user_id_str not in casino.data["users"]:
            casino.data["users"][user_id_str] = {}
        casino.data["users"][user_id_str]["username"] = username
        casino.save_data()

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
🎫 /promo <kod> - Iskoristi promo kod
💸 /cashout <iznos> - Zatraži isplatu
❓ /help - Pomoć
        """

        await update.message.reply_text(welcome_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in start_command: {e}")
        await update.message.reply_text("❌ Došlo je do greške. Molimo pokušajte ponovo.")

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prikazuje balans korisnika"""
    try:
        user_id = update.effective_user.id
        balance = casino.get_user_balance(user_id)

        user_id_str = str(user_id)
        if user_id_str in casino.data.get("users", {}):
            user_data = casino.data["users"][user_id_str]
            total_wagered = int(user_data.get("total_wagered", 0))
            total_won = int(user_data.get("total_won", 0))
            used_promo_codes = len(user_data.get("used_promo_codes", []))
        else:
            total_wagered = 0
            total_won = 0
            used_promo_codes = 0

        await update.message.reply_text(
            f"💰 **Vaš balans:** {balance:,} RSD\n\n"
            f"📊 **Statistike:**\n"
            f"🎲 Ukupno uloženo: {total_wagered:,} RSD\n"
            f"🏆 Ukupno dobijeno: {total_won:,} RSD\n"
            f"📈 Neto: {total_won - total_wagered:+,} RSD\n"
            f"🎫 Iskorišćeni promo kodovi: {used_promo_codes}", 
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in balance_command: {e}")
        await update.message.reply_text("❌ Došlo je do greške. Molimo pokušajte ponovo.")

async def work_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Work komanda - daje 30 RSD svakih 3 dana"""
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username or f"User_{user_id}"

        can_work, next_work_time = casino.can_work(user_id)

        if not can_work and next_work_time:
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

        work_amount = 30
        old_balance = casino.get_user_balance(user_id)
        new_balance = casino.update_balance(user_id, work_amount)
        casino.set_work_time(user_id)

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

async def promo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Komanda za korišćenje promo koda"""
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username or f"User_{user_id}"
        
        # Ažuriraj username
        user_id_str = str(user_id)
        if user_id_str not in casino.data["users"]:
            casino.data["users"][user_id_str] = {}
        casino.data["users"][user_id_str]["username"] = username
        casino.save_data()

        if not context.args:
            await update.message.reply_text(
                "❌ Molimo unesite promo kod!\n"
                "Primer: /promo WELCOME100"
            )
            return

        promo_code = context.args[0].upper()
        old_balance = casino.get_user_balance(user_id)
        
        success, message, amount = casino.use_promo_code(user_id, promo_code)
        
        if success:
            new_balance = casino.get_user_balance(user_id)
            await update.message.reply_text(
                f"🎉 **PROMO KOD USPEŠNO ISKORIŠĆEN!** 🎉\n\n"
                f"🎫 Kod: **{promo_code}**\n"
                f"💰 Bonus: +{amount:,} RSD\n"
                f"💳 Stari balans: {old_balance:,} RSD\n"
                f"💳 Novi balans: {new_balance:,} RSD",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(message)
            
    except Exception as e:
        logger.error(f"Error in promo_command: {e}")
        await update.message.reply_text("❌ Došlo je do greške. Molimo pokušajte ponovo.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Help komanda sa svim dostupnim komandama"""
    try:
        user_id = update.effective_user.id

        help_text = f"""
🎰 **CASINO BOT - KOMANDE** 🎰

**🎮 Igre (House Edge: 10%):**
🃏 /play <ulog> - Blackjack
🎰 /roulette <ulog> - Rulet (zatim izaberi opciju)
🎲 /dice <ulog> <brojevi> - Dice (1-3 broja od 1-6)
🪙 /flip <ulog> <heads/tails> - Coinflip

**💰 Balans:**
💳 /bal - Proveri balans i statistike
💼 /work - Radi za 30 RSD (svaka 3 dana)
🎫 /promo <kod> - Iskoristi promo kod
💸 /cashout <iznos> - Zatraži isplatu (min. 1,000 RSD)

**ℹ️ Ostalo:**
🏠 /start - Početna poruka
❓ /help - Ova poruka

**📏 Minimalni ulog:** 10 RSD na sve igre
        """

        if user_id == ADMIN_ID:
            help_text += """

**🔧 Admin komande:**
➕ /add <user_id> <iznos> - Dodaj balans
➖ /remove <user_id> <iznos> - Oduzmi balans  
🏦 /house - House balans i detaljne statistike
💸 /cashouts - Upravljanje cashout zahtevima
📡 /broadcast <poruka> - Pošalji poruku svim korisnicima

**🎫 Promo kod komande:**
🎁 /create_promo <kod> <iznos> <max_korišćenja> [dani] - Kreiraj promo kod
📊 /promo_stats - Upravljanje promo kodovima
            """

        await update.message.reply_text(help_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in help_command: {e}")
        await update.message.reply_text("❌ Došlo je do greške. Molimo pokušajte ponovo.")

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

        old_balance = casino.get_user_balance(target_user_id)
        new_balance = casino.update_balance(target_user_id, amount)

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

async def house_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin komanda za prikaz house balansa i statistika"""
    try:
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Nemate dozvolu za ovu komandu!")
            return

        house_balance = casino.data.get("house_balance", 0)
        total_users = len(casino.data.get("users", {}))
        
        total_user_balance = 0
        for user in casino.data.get("users", {}).values():
            if isinstance(user, dict):
                total_user_balance += int(user.get("balance", 0))

        stats = casino.data.get("stats", {})
        total_games = sum(int(game_stat.get("games", 0)) for game_stat in stats.values())
        total_house_profit = sum(int(game_stat.get("profit", 0)) for game_stat in stats.values())

        promo_codes = casino.data.get("promo_codes", {})
        total_promo_given = sum(int(code_data.get("amount", 0)) * int(code_data.get("current_uses", 0)) 
                               for code_data in promo_codes.values())
        active_promo_codes = sum(1 for p in promo_codes.values() if p.get("active", True))

        recent_games = casino.data.get("game_history", [])[-50:]
        rigged_count = sum(1 for game in recent_games if game.get("rigged", False))

        total_wagered = sum(int(user.get("total_wagered", 0)) for user in casino.data.get("users", {}).values() if isinstance(user, dict))
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
            f"🎫 **Promo kodovi:**\n"
            f"📦 Ukupno: {len(promo_codes)}\n"
            f"✅ Aktivni: {active_promo_codes}\n"
            f"💸 Ukupno dodeljeno: {total_promo_given:,} RSD\n\n"
            f"🎯 **House Edge:**\n"
            f"📈 Cilj: 10.00%\n"
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

async def create_promo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin komanda za kreiranje promo kodova"""
    try:
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Nemate dozvolu za ovu komandu!")
            return

        if len(context.args) < 3:
            await update.message.reply_text(
                "❌ Molimo unesite sve potrebne podatke!\n\n"
                "**Korišćenje:**\n"
                "/create_promo <kod> <iznos> <max_korišćenja> [dani_do_isteka]\n\n"
                "**Primeri:**\n"
                "• `/create_promo WELCOME100 100 50` - 100 RSD, 50 korišćenja, ne ističe\n"
                "• `/create_promo BONUS500 500 20 7` - 500 RSD, 20 korišćenja, ističe za 7 dana\n"
                "• `/create_promo VIP1000 1000 10 30` - 1000 RSD, 10 korišćenja, ističe za 30 dana"
            )
            return

        try:
            code = context.args[0].upper()
            amount = int(context.args[1])
            max_uses = int(context.args[2])
            
            if amount <= 0:
                await update.message.reply_text("❌ Iznos mora biti pozitivan!")
                return
                
            if max_uses <= 0:
                await update.message.reply_text("❌ Broj korišćenja mora biti pozitivan!")
                return
            
            expires_at = None
            if len(context.args) > 3:
                days = int(context.args[3])
                if days > 0:
                    expires_at = datetime.now() + timedelta(days=days)
            
        except ValueError:
            await update.message.reply_text("❌ Iznos, broj korišćenja i dani moraju biti brojevi!")
            return

        success = casino.create_promo_code(code, amount, max_uses, expires_at)
        
        if success:
            expiry_text = f"📅 Ističe: {expires_at.strftime('%d.%m.%Y %H:%M')}" if expires_at else "⏰ Ne ističe"
            
            await update.message.reply_text(
                f"✅ **PROMO KOD KREIRAN!**\n\n"
                f"🎫 Kod: **{code}**\n"
                f"💰 Iznos: {amount:,} RSD\n"
                f"🔢 Maksimalno korišćenja: {max_uses}\n"
                f"{expiry_text}\n\n"
                f"Korisnici mogu da koriste: `/promo {code}`",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Promo kod sa tim nazivom već postoji!")
            
    except Exception as e:
        logger.error(f"Error in create_promo_command: {e}")
        await update.message.reply_text("❌ Došlo je do greške. Molimo pokušajte ponovo.")

# IGRE - BLACKJACK
class BlackjackGame:
    def __init__(self, user_id: int, bet: int):
        self.user_id = user_id
        self.bet = bet
        self.deck = self.create_deck()
        self.player_hand = []
        self.dealer_hand = []
        self.game_over = False
        self.rigged = casino.is_rigged_game()

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
        self.player_hand = [self.deal_card(), self.deal_card()]
        self.dealer_hand = [self.deal_card(), self.deal_card()]

        if self.rigged:
            if self.calculate_hand_value(self.dealer_hand) < 17:
                good_cards = [10, 9, 8]
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
        """Završava igru"""
        self.game_over = True
        player_value = self.calculate_hand_value(self.player_hand)

        while self.calculate_hand_value(self.dealer_hand) < 17:
            new_card = self.deal_card()
            self.dealer_hand.append(new_card)

        dealer_value = self.calculate_hand_value(self.dealer_hand)

        if self.rigged and action not in ["bust"]:
            if dealer_value > 21 and random.random() < 0.8:
                self.dealer_hand[-1] = random.choice([1, 2, 3, 4, 5, 6])
                dealer_value = self.calculate_hand_value(self.dealer_hand)
            elif dealer_value < player_value and dealer_value < 21 and random.random() < 0.7:
                needed_points = min(21, player_value + 1) - dealer_value
                if needed_points <= 10:
                    self.dealer_hand[-1] = min(10, needed_points)
                    dealer_value = self.calculate_hand_value(self.dealer_hand)

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

        new_balance = casino.update_balance(self.user_id, payout)
        casino.update_wager(self.user_id, self.bet)
        casino.update_stats("blackjack", -payout)

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

        game = BlackjackGame(user_id, bet)
        active_blackjack_games[user_id] = game

        game_text = game.start_game()

        if not game.game_over:
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

# ROULETTE IGRA
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
    """Rukuje rulet opcijama"""
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

        rigged = casino.is_rigged_game()

        if rigged:
            losing_numbers = []

            if choice == "red":
                losing_numbers = [0] + [i for i in range(1, 37) if i not in [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]]
            elif choice == "black":
                losing_numbers = [0] + [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
            elif choice == "even":
                losing_numbers = [0] + list(range(1, 37, 2))
            elif choice == "odd":
                losing_numbers = [0] + list(range(2, 37, 2))
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

            if losing_numbers and random.random() < 0.85:
                number = random.choice(losing_numbers)
            else:
                number = random.randint(0, 36)
        else:
            number = random.randint(0, 36)

        await query.edit_message_text("🎰 Rulet se okreće... 🎰")
        await asyncio.sleep(1)
        await query.edit_message_text("🎰 Rulet se okreće... 🌀")
        await asyncio.sleep(1)
        await query.edit_message_text("🎰 Rulet se zadržava... ⏱️")
        await asyncio.sleep(1)

        red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
        color = "🔴" if number in red_numbers else "⚫" if number != 0 else "🟢"

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

        new_balance = casino.update_balance(user_id, payout)
        casino.update_wager(user_id, bet)
        casino.update_stats("roulette", -payout)

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
        else:
            await query.answer("❌ Nepoznata komanda!")
    except Exception as e:
        logger.error(f"Error in main_callback_handler: {e}")
        if update.callback_query:
            await update.callback_query.answer("❌ Došlo je do greške.")

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
        application = Application.builder().token(BOT_TOKEN).build()

        # Registracija komandi
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("bal", balance_command))
        application.add_handler(CommandHandler("work", work_command))

        # Igre
        application.add_handler(CommandHandler("play", play_blackjack))
        application.add_handler(CommandHandler("roulette", roulette_game))

        # Promo kod sistem
        application.add_handler(CommandHandler("promo", promo_command))
        application.add_handler(CommandHandler("create_promo", create_promo_command))

        # Admin komande
        application.add_handler(CommandHandler("add", add_balance_command))
        application.add_handler(CommandHandler("house", house_balance_command))

        # Callback handlers
        application.add_handler(CallbackQueryHandler(main_callback_handler))

        # Error handler
        application.add_error_handler(error_handler)

        print("🎰 Casino bot je pokrenuo!")
        print(f"📁 Podaci se čuvaju u: {DATA_FILE}")
        print(f"🔧 Admin ID: {ADMIN_ID}")
        print(f"📊 House Edge: {HOUSE_EDGE*100}%")
        print(f"⚙️ Rigging Probability: {RIGGING_PROBABILITY*100}%")

        application.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        print(f"❌ Greška pri pokretanju bota: {e}")

if __name__ == '__main__':
    main()
