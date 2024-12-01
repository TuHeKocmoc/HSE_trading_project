# 📊 Portfolio Builder

This project is a Python script that automates the creation of a diversified investment portfolio by analyzing stocks
and cryptocurrencies. It fetches financial data, calculates metrics, ranks assets, and allocates funds based on
customizable criteria.

## Features

    •   Automated data retrieval: Fetches stock data using the Tinkoff API and cryptocurrency data using OKX and CoinGecko APIs.
    •   Customizable metrics: Calculates metrics like P/E ratio, P/B ratio, returns, liquidity, volatility, and more.
    •   Dynamic portfolio allocation: Allocates capital dynamically based on asset ratings, ensuring significant investments in top-performing assets.
    •   Visualization: Generates a pie chart to visualize portfolio allocation.
    •   Robust error handling: Includes error handling and retry mechanisms for API requests.

## Setup

    1.  Clone the repository.
    2.  Install required packages:

pip install -r requirements.txt

    3.  Set up environment variables:
    •   Create a .env file in the project root directory.
    •   Add your API keys and tokens:

TOKEN=your_tinkoff_token
API_KEY=your_okx_api_key
SECRET_KEY=your_okx_secret_key
PASSPHRASE=your_okx_passphrase

## Usage

    1.  Run the script:

python main.py

    2.  Enter your total capital when prompted.
    3.  View the generated portfolio in portfolio.csv and the displayed pie chart.

Dependencies

    •   Python 3.x
    •   Libraries: httpx, tinkoff-invest, pandas, numpy, matplotlib, tqdm, pycoingecko, requests, python-dotenv

Important notes

    •   Ensure your API keys are valid and have the necessary permissions.
    •   Be mindful of API rate limits to avoid being blocked.
    •   This script is for educational purposes and does not constitute financial advice.
    •   The first run may take some time due to the large volume of data.
    •   Download all_metrics.csv for a quick start.

## License

This project is licensed under the CC-BY License.

# 📊 Построитель Портфолио

Этот проект представляет собой скрипт на Python, который автоматизирует создание диверсифицированного инвестиционного
портфеля путем анализа акций и криптовалют. Он получает финансовые данные, вычисляет метрики, ранжирует активы и
распределяет средства на основе настраиваемых критериев.

## Функции

    •   Автоматический сбор данных: Получает данные об акциях через API Тинькофф и данные о криптовалютах через API OKX и CoinGecko.
    •   Настраиваемые метрики: Вычисляет метрики, такие как коэффициенты P/E и P/B, доходность, ликвидность, волатильность и другие.
    •   Динамическое распределение портфеля: Динамически распределяет капитал на основе рейтингов активов, обеспечивая значительные инвестиции в топовые активы.
    •   Визуализация: Генерирует круговую диаграмму для визуализации распределения портфеля.
    •   Надежная обработка ошибок: Включает обработку ошибок и механизмы повторных попыток для API-запросов.

## Настройка

    1.  Клонируйте репозиторий.
    2.  Установите необходимые пакеты:

## pip install -r requirements.txt

    3.  Настройте переменные окружения:
    •   Создайте файл .env в корневой директории проекта.
    •   Добавьте ваши API ключи и токены:

TOKEN=ваш_токен_тинькофф
API_KEY=ваш_okx_api_key
SECRET_KEY=ваш_okx_secret_key
PASSPHRASE=ваш_okx_passphrase

## Использование

    1.  Запустите скрипт:

python main.py

    2.  Введите ваш общий капитал по запросу.
    3.  Просмотрите сгенерированный портфель в файле portfolio.csv и на отображаемой диаграмме.

## Зависимости

    •   Python 3.x
    •   Библиотеки: httpx, tinkoff-invest, pandas, numpy, matplotlib, tqdm, pycoingecko, requests, python-dotenv

## Важные замечания

    •   Убедитесь, что ваши API ключи действительны и имеют необходимые разрешения.
    •   Соблюдайте ограничения по частоте запросов к API, чтобы избежать блокировки.
    •   Этот скрипт предназначен для образовательных целей и не является финансовой рекомендацией.
    •   Первый запуск может занять некоторое время из-за большого объема данных.
    •   Скачайте all_metrics.csv для быстрого запуска.

## Лицензия

Этот проект лицензирован по лицензии CC-BY.

😊 Желаем удачных инвестиций!
