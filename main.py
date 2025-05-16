import asyncio
import re
import os
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import CommandStart

BOT_TOKEN = os.environ['compensation_key']

craft_dict = {
    "service carabine": 32,
    "assault smg": 12,
    "carbine rifle": 32,
    "military rifle": 32,
    "special rifle": 32,
    "battle rifle": 32,
    "pump shotgun mk2": 13,
    "combat shotgun": 32,
    "assault shotgun": 32,
    "heavy shotgun": 32,
    "pump shotgun": 7,
    "тяжелый пистолет": 5,
    "tactical smg": 12,
    "ar пистолет": 12,
    "кольт": 50,
    "smg": 12,
    "светошумовая граната": 50,
    "сигнальная ракетница": 5,
    "дымовой гранатомет": 50,
    "резиновая дубинка": 3,
    "фонарик": 3,
    "броня": 3,
    "тазер": 3,
    "gusenberg sweeper": 50,
    "compact rifle": 20,
    "assault rifle": 20,
    "обрез": 8,
    "старинный пистолет": 3,
    "револьвер": 50,
    "пистолет": 3,
    "micro smg": 9,
    "smg-mk2": 9,
    "коктейль молотова": 100,
    "анальгетик": 0,
    "sniper rifle" : 0
}

fractions = [
    "F_EMS", "F_FIB", "F_LSPD", "F_LSSD", "F_NEWS", "F_LSARMY", "F_PRISON", "F_LSCITYHALL",
    "F_YAKUZA", "F_ITALYMAFIA", "F_MEXICOMAFIA", "F_RUSSIANMAFIA", "F_ARMENIAMAFIA",
    "F_GANG_VAGOS", "F_GANG_GROVE", "F_GANG_BALLAS", "F_GANG_BLOODS", "F_GANG_MARABUNTA"
]

router = Router()
user_materials = {}

def normalize_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r"\([^)]*\)", "", name).strip()
    name = re.sub(r"броня.*", "броня", name)

    for key in craft_dict:
        if key in name:
            return key
    return name

def calculate_materials(text: str):
    items = re.findall(r'([^,]+?) x(\d+)', text)
    result = {}
    total = 0
    analgesic_count = 0

    for item_name, count in items:
        name = normalize_name(item_name.strip())
        count = int(count)

        if name == "анальгетик":
            analgesic_count += count
            materials = 0  # не считаем в материалы
        elif name in ["7.62mm", "5.56mm", "12mm", "11.43mm", "9mm"]:
            if name == "7.62mm":
                mags = -(-count // 30)
                materials = mags * 5
            elif name == "5.56mm":
                mags = -(-count // 30)
                materials = mags * 3
            elif name == "12mm":
                mags = -(-count // 8)
                materials = mags * 3
            elif name == "11.43mm":
                mags = -(-count // 12)
                materials = mags * 6
            elif name == "9mm":
                mags = -(-count // 20)
                materials = mags * 2
        else:
            materials = craft_dict.get(name, 0) * count

        if name != "анальгетик":
            result[name] = result.get(name, 0) + materials
            total += materials

    return result, total, analgesic_count

def get_fraction_keyboard():
    builder = InlineKeyboardBuilder()
    for f in fractions:
        builder.button(text=f, callback_data=f"fraction_{f}")
    builder.adjust(2)
    return builder.as_markup()

@router.message(F.text)
async def handle_message(message: Message):
    original_text = message.text

    # Извлекаем user_id_str, например: Viktor_Psih [420548]
    user_id_match = re.match(r"^([^\d\n]*\[\d+\])", original_text)
    user_id_str = user_id_match.group(1).strip() if user_id_match else None

    # Удаляем всё до первого упоминания вида "название (что-то) xчисло"
    item_start = re.search(r'\w.+?\s+\(.*?\)\s*(\(.*?\))?\s*x\d+', original_text)
    if item_start:
        text = original_text[item_start.start():]
    else:
        text = original_text  # если шаблон не найден, используем как есть

    # Продолжение обработки
    special_items = []

    materials, total, analgesic = calculate_materials(text)

    # Поиск "Катана (...)", "Нож (...)", "Sniper Rifle (...) (...)"
    katana_matches = re.findall(r'(Катана\s*\([^)]+\))', text, re.IGNORECASE)
    knife_matches = re.findall(r'(Нож\s*\([^)]+\))', text, re.IGNORECASE)
    sniper_matches = re.findall(r'(Sniper Rifle)\s*\(([^)]+)\)\s*\(([^)]+)\)', text, re.IGNORECASE)

    special_items.extend(katana_matches)
    special_items.extend(knife_matches)
    for name, code, percent in sniper_matches:
        special_items.append(f"{name} ({code}) ({percent})")

    user_materials[message.from_user.id] = {
        "total": total,
        "analgesic": analgesic,
        "special_items": special_items,
        "user_id_str": user_id_str
    }

    # Формируем ответ
    lines = [f"{name.title()} — <b>{amount} материалов</b>" for name, amount in materials.items()]
    lines.append(f"\n<b>Итого: {total} материалов</b>")

    await message.answer("\n".join(lines), reply_markup=get_fraction_keyboard())

@router.callback_query(F.data.startswith("fraction_"))
async def handle_fraction(callback: CallbackQuery):
    faction = callback.data.replace("fraction_", "")

    data = user_materials.get(callback.from_user.id, {
        "total": 0,
        "analgesic": 0,
        "special_items": [],
        "user_id_str": None
    })

    total = data.get("total", 0)
    analgesic = data.get("analgesic", 0)
    special_items = data.get("special_items", [])
    user_id_str = data.get("user_id_str")

    await callback.answer()

    # Первое сообщение: материалы и анальгетики
    msg_lines = [f"faction_give_item {faction} {total} Материалы"]
    if analgesic > 0:
        msg_lines.append(f"faction_give_item {faction} {analgesic} Анальгетик")

    await callback.message.answer("\n".join(msg_lines))

    # Второе сообщение: особые предметы с заголовком "Выдать Ник [Статик]:
    if special_items:
        special_lines = []
        for item in special_items:
            if item != user_id_str:
                special_lines.append(item)

        if user_id_str:
            header = f"Выдать {user_id_str}:"
        else:
            header = "Выдать:"

        await callback.message.answer(header + "\n" + "\n".join(special_lines))

async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
