# MAI Schedule Telegram Bot — Linux

Telegram-бот расписания МАИ на Python + aiogram 3.

## Самый простой запуск на Ubuntu/Debian

Распакуй архив:

```bash
unzip mai_schedule_bot_linux.zip
cd mai_schedule_bot_linux
```

Запусти установщик:

```bash
chmod +x install.sh
sudo ./install.sh
```

Он:
- установит Python 3, pip и venv;
- создаст системного пользователя `mai-bot`;
- скопирует проект в `/opt/mai-schedule-bot`;
- создаст виртуальное окружение;
- установит зависимости;
- создаст systemd-сервис;
- включит автозапуск после перезагрузки.

После установки открой:

```bash
sudo nano /opt/mai-schedule-bot/.env
```

И впиши:

```env
BOT_TOKEN=123456789:YOUR_BOT_TOKEN
DB_PATH=bot.db
CACHE_TTL_SECONDS=900
SEMESTER_START=
```

Запусти бота:

```bash
sudo systemctl start mai-schedule-bot
```

Статус:

```bash
sudo systemctl status mai-schedule-bot
```

Логи в реальном времени:

```bash
sudo journalctl -u mai-schedule-bot -f
```

Перезапуск:

```bash
sudo systemctl restart mai-schedule-bot
```

Остановка:

```bash
sudo systemctl stop mai-schedule-bot
```

Автозапуск включается установщиком:

```bash
sudo systemctl enable mai-schedule-bot
```

## Обновление файлов проекта

Если потом меняешь код:

```bash
sudo systemctl stop mai-schedule-bot
sudo cp -r app bot.py requirements.txt /opt/mai-schedule-bot/
sudo chown -R mai-bot:mai-bot /opt/mai-schedule-bot
sudo systemctl start mai-schedule-bot
```

Если изменился `requirements.txt`:

```bash
sudo /opt/mai-schedule-bot/.venv/bin/pip install -r /opt/mai-schedule-bot/requirements.txt
sudo systemctl restart mai-schedule-bot
```

## Ручной запуск без systemd

Для теста:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
python bot.py
```

## Где лежат данные

После установки:

```text
/opt/mai-schedule-bot/
├── bot.py
├── app/
├── .env
├── .venv/
└── bot.db
```

`bot.db` — SQLite с Telegram ID пользователей и их выбранными группами.


## Проверка парсера без Telegram

После установки можно отдельно проверить получение расписания:

```bash
cd /opt/mai-schedule-bot
sudo -u mai-bot .venv/bin/python test_mai.py
```

В исправленной версии клиент повторяет браузерную схему МАИ:
сначала открывает `groups.php`, получает PHP-сессию, затем выставляет
`schedule-st-group` и только после этого запрашивает `index.php`.
