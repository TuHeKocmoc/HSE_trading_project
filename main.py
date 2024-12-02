# Импорт библиотек
from httpx import ReadTimeout
from tinkoff.invest import Client, CandleInterval, RequestError
import pandas as pd
from datetime import datetime, timedelta, timezone
from okx.MarketData import MarketAPI
import numpy as np
import matplotlib.pyplot as plt
from tqdm.asyncio import tqdm
from pycoingecko import CoinGeckoAPI
import requests
import time
import os
from dotenv import load_dotenv


def get_transaction_data(coingecko_id):
    """
    Получает объем транзакций и
    циркулирующее предложение используя CoinGeckoAPI
    :param coingecko_id: ID криптовалюты в системе Gecko
    :return: Словарь с объемом транзакций ($) и циркулирующим предложением
    """
    print("Получаю объем транзакций и circulating supply...")
    url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}"

    try:
        response = requests.get(url) # Выполняем GET-запрос к API CoinGecko
    except requests.exceptions.ConnectionError as e:
        # Обработка ошибки соединения
        print("Проблема: ", e)
        print("Повторяю попытку...")
        time.sleep(10)
        return get_transaction_data(coingecko_id)

    if response.status_code in [429, 503, 504]:
        # Если слишком много запросов или сервер недоступен, ждем и повторяем
        retry_after = response.headers.get('Retry-After')
        wait_time = int(retry_after) if retry_after else 10
        print(f"Жду {wait_time} секунд перед повторной попыткой...")
        time.sleep(wait_time)
        return get_transaction_data(coingecko_id)
    elif response.status_code == 404:
        # Если ресурс не найден, возвращаем нулевые значения
        print("Проблема: ", response)
        return {
            "transaction_volume_usd": 0,
            "circulating_supply": 0
        }
    elif response.status_code != 200:
        # Если другой код ошибки, выбрасываем исключение
        raise Exception(
            f"Не удалось получить информацию для {coingecko_id}: "
            f"{response.status_code}")

    # Преобразуем ответ в формат JSON
    data = response.json()

    # Извлекаем данные о транзакционном объеме и циркулирующем предложении
    transaction_volume = (data.get("market_data", {})
                          .get("total_volume", {}).get("usd"))

    circulating_supply = (data.get("market_data", {})
                          .get("circulating_supply"))

    # Если данные отсутствуют, устанавливаем значение 0
    if transaction_volume is None:
        transaction_volume = 0
    if circulating_supply is None:
        circulating_supply = 0

    return {
        "transaction_volume_usd": transaction_volume,
        "circulating_supply": circulating_supply
    }


# Загружаем переменные окружения из файла .env
load_dotenv()

# Получаем значения переменных окружения
TOKEN = os.getenv("TOKEN")
api_key = os.getenv("API_KEY")
secret_key = os.getenv("SECRET_KEY")
passphrase = os.getenv("PASSPHRASE")
all_metrics = []
metrics_file = "all_metrics.csv"

# Проверяем, что все необходимые переменные загружены
if not all([TOKEN, api_key, secret_key, passphrase]):
    raise ValueError("Не все переменные окружения загружены. "
                     "Проверьте файл .env.")

print("Переменные успешно загружены из .env!")

if os.path.exists(metrics_file):
    # Если файл с метриками уже существует, загружаем данные из него
    print(f"Файл {metrics_file} уже существует. "
          f"Пропускаю обработку акций и криптовалют...")
    metrics_df = pd.read_csv(metrics_file)
    for _, row in metrics_df.iterrows():
        # Восстанавливаем данные о метриках из файла
        if 'ticker' in row and pd.notna(row['ticker']):
            all_metrics.append({
                "ticker": row['ticker'],
                "pe": row.get('pe', None),
                "pb": row.get('pb', None),
                "returns": row.get('returns', 0),
                "liquidity": row.get('liquidity', 0),
                "rating": row.get('rating', 0)
            })
        elif 'symbol' in row and pd.notna(row['symbol']):
            all_metrics.append({
                "symbol": row['symbol'],
                "returns": row.get('returns', 0),
                "volatility": row.get('volatility', 0),
                "liquidity": row.get('liquidity', 0),
                "rating": row.get('rating', 0)
            })

    print("Данные преобразованы в all_metrics!")
else:
    # Если файла нет, начинаем обработку акций
    print('Начинаю обрабатывать акции...')

    with Client(TOKEN) as client:
        # Получаем список всех доступных акций
        instruments = client.instruments.shares().instruments

        for stock in tqdm(instruments, desc="Акции", unit="акция"):
            flag = False
            while not flag:
                try:
                    # Уникальный идентификатор финансового инструмента
                    figi = stock.figi
                    issue_size = stock.issue_size # Объем выпуска акций

                    # Получаем исторические данные по свечам за последний год
                    history = client.market_data.get_candles(
                        figi=figi,
                        from_=datetime.now(timezone.utc) - timedelta(days=365),
                        to=datetime.now(timezone.utc),
                        interval=CandleInterval.CANDLE_INTERVAL_DAY
                    )

                    # Извлекаем цены закрытия
                    prices = [float(candle.close.units +
                                    candle.close.nano / 1e9)
                              for candle in history.candles]

                    if prices:
                        last_price = prices[-1] # Последняя цена
                        # Доходность
                        returns = ((last_price - prices[0]) / prices[0]) * 100
                    else:
                        last_price = 0
                        returns = 0

                    if history.candles:
                        volumes = [candle.volume for candle in history.candles]
                        liquidity = np.mean(volumes) # Средний объем торгов
                    else:
                        volumes = []
                        liquidity = 0

                    # Номинальная стоимость акции
                    nominal_value = (stock.nominal.units +
                                     stock.nominal.nano / 1e9)
                    # Рыночная капитализация
                    market_cap = last_price * issue_size
                    # Условная чистая прибыль (10% от капитализации)
                    net_income = market_cap * 0.1
                    # Прибыль на акцию
                    eps = net_income / issue_size if issue_size else None
                    pe = last_price / eps if eps else None # Коэффициент P/E

                    if issue_size and nominal_value:
                        # Балансовая стоимость компании
                        book_value = issue_size * nominal_value
                        # Балансовая стоимость на акцию
                        book_value_per_share = book_value / issue_size
                        # Коэффициент P/B
                        pb = last_price / book_value_per_share
                    else:
                        book_value = None
                        book_value_per_share = None
                        pb = None

                    # Оценка коэффициента P/E
                    if pe and pe < 15:
                        pe_score = 1
                    elif pe and pe < 25:
                        pe_score = 0.25
                    else:
                        pe_score = 0

                    # Оценка коэффициента P/B
                    if pb and pb < 1.5:
                        pb_score = 1
                    elif pb and pb < 3:
                        pb_score = 0.5
                    else:
                        pb_score = 0

                    # Нормализуем доходность и ликвидность в диапазон [0,1]
                    returns_score = np.clip(returns / 10, 0, 1)
                    liquidity_score = np.clip(liquidity / 1_000_000, 0, 1)

                    # Рассчитываем общий рейтинг акции
                    total_score = (
                            0.4 * pe_score +
                            0.3 * pb_score +
                            0.2 * returns_score +
                            0.1 * liquidity_score
                    )

                    # Добавляем метрики акции в общий список
                    all_metrics.append({
                            "ticker": stock.ticker,
                            "pe": pe,
                            "pb": pb,
                            "returns": returns,
                            "liquidity": liquidity,
                            'rating': total_score
                    })

                    flag = True

                except RequestError as e:
                    # Обработка ошибок запроса к API
                    print("Проблема: ", e)
                    ratelimit_reset = 10
                    if e.metadata and hasattr(e.metadata, "ratelimit_reset"):
                        ratelimit_reset = int(e.metadata.ratelimit_reset)
                    print(f"Ожидание {ratelimit_reset} секунд...")
                    time.sleep(ratelimit_reset)

    print('Обработка акций завершена')
    print('Подключаюсь к API для криптовалют...')

    market_api = MarketAPI(api_key, secret_key, passphrase, False, '0')
    # Получаем список доступных торговых пар на спотовом рынке
    tickers = market_api.get_tickers(instType='SPOT')['data']

    print("OKX подключен...")

    cg = CoinGeckoAPI()
    coins = cg.get_coins_list() # Получаем список всех доступных криптовалют
    # Создаем словарь для сопоставления символов криптовалют
    # с их ID на CoinGecko
    mapping = {coin['symbol']: coin['id'] for coin in coins}
    print("CoinGecko подключен...")

    print('Подключился')
    print('Начинаю обрабатывать криптовалюты...')

    for symbol in tqdm(tickers, desc="Криптовалюты", unit="пара"):
        flag = False
        while not flag:
            try:
                liquidity = float(symbol['vol24h']) # Объем торгов за 24 часа
                price = float(symbol['last']) # Текущая цена
                inst_id = symbol['instId'] # Идентификатор инструмента
                print("Получаю OKX дату...")
                # Получаем исторические данные по свечам
                response = market_api.get_candlesticks(instId=inst_id,
                                                       bar='1D')
                print("Получено...")
                data = response['data']

                columns = [
                    'timestamp', 'open', 'high', 'low', 'close',
                    'volume', 'quote_volume', 'redundant_quote_volume', 'flag'
                ]

                # Создаем DataFrame из полученных данных
                df = pd.DataFrame(data, columns=columns)

                # Преобразуем временные метки в формат datetime
                df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int),
                                                 unit='ms')

                numeric_columns = ['open', 'high', 'low', 'close', 'volume',
                                   'quote_volume']
                # Преобразуем числовые столбцы в тип float
                df[numeric_columns] = df[numeric_columns].astype(float)

                # Рассчитываем процентное изменение и волатильность
                df["pct_change"] = df["close"].pct_change()
                df["volatility"] = df["pct_change"].abs() * 100
                max_volatility = df["volatility"].max()

                if not df.empty:
                    # Рассчитываем доходность и волатильность
                    returns = ((df['close'].iloc[-1] - df['close'].iloc[0])
                               / df['close'].iloc[0]) * 100
                    volatility = df['close'].pct_change().std() * 100
                else:
                    returns = 0
                    volatility = 0

                print("Получаю CoinGecko дату...")
                # Получаем идентификатор криптовалюты для CoinGecko
                coingecko_id = mapping.get(inst_id.split('-')[0].lower(), None)
                # Получаем данные о транзакционном объеме
                # и циркулирующем предложении
                coingecko_data = get_transaction_data(coingecko_id)
                print("Получено!")

                daily_transaction_volume = coingecko_data[
                    'transaction_volume_usd'
                ]
                circulating_supply = coingecko_data['circulating_supply']

                # Рыночная капитализация
                market_cap = price * circulating_supply

                # Рассчитываем отношение цены к объему
                pv_ratio = price / liquidity if liquidity > 0 else None

                # Рассчитываем коэффициент NVT и его оценку
                if daily_transaction_volume > 0:
                    nvt_ratio = market_cap / daily_transaction_volume
                    nvt_score = 1 / (nvt_ratio + 1)
                else:
                    nvt_ratio = None
                    nvt_score = 0

                # Нормализуем оценки в диапазон [0,1]
                returns_score = np.clip(returns / 10, 0, 1)
                liquidity_score = np.clip(liquidity / 1_000_000, 0, 1)

                pv_score = 1 / (pv_ratio + 1) if pv_ratio is not None else 0

                if max_volatility:
                    volatility_score = 1 - min(volatility / max_volatility, 1)
                else:
                    volatility_score = None

                # Рассчитываем общий рейтинг криптовалюты
                total_score = (
                        0.3 * nvt_score +
                        0.2 * pv_score +
                        0.3 * returns_score +
                        0.1 * liquidity_score +
                        0.1 * volatility_score
                )
                # Добавляем метрики криптовалюты в общий список
                all_metrics.append({
                    "symbol": inst_id,
                    "returns": returns,
                    "volatility": volatility,
                    "liquidity": liquidity,
                    "rating": total_score
                })
                flag = True
            except ReadTimeout as e:
                # Обработка ошибки тайм-аута при чтении данных
                print("Проблема: ", e)
                print("Повторяю попытку...")
                time.sleep(10)
                continue

    print('Закончил обрабатывать криптовалюты')

    # Сохраняем все метрики в файл CSV
    metrics_df = pd.DataFrame(all_metrics)
    metrics_df.to_csv(metrics_file, index=False, encoding="utf-8")

    print(f"Данные all_metrics сохранены в {metrics_file}")

print('Начинаю делать портфолио...')

# Запрашиваем у пользователя общий капитал для инвестирования ($)
total_capital = int(input("Введите капитал ($): "))

# Сортируем активы по рейтингу в порядке убывания
all_metrics.sort(key=lambda x: x['rating'], reverse=True)

# Фильтруем активы по ликвидности
filtered_assets = [asset for asset in all_metrics
                   if asset.get('liquidity', 0) >= 10_000]

# Устанавливаем минимальный и максимальный процент вложений в один актив
min_percentage = 1
max_percentage = 30
max_capital_per_asset = total_capital * max_percentage / 100
min_capital_per_asset = total_capital * min_percentage / 100
portfolio = []
remaining_capital = total_capital
N = min(10, len(filtered_assets))  # Ограничение на кол-во различных активов
filtered_assets = filtered_assets[:N]
total_weight = sum(range(1, N + 1)) # Сумма весов

for i, asset in enumerate(filtered_assets):
    if remaining_capital <= 0:
        break

    weight = N - i  # Рассчитываем вес актива (на основе рейтинга)
    percentage = (weight / total_weight) * 100
    percentage = max(percentage, min_percentage)
    percentage = min(percentage, max_percentage)

    # Получаем сумму, на которую актив должен быть приобретен
    allocation = total_capital * (percentage / 100)
    # Учитываем комиссию 0.04%
    allocation_after_commission = allocation * 0.9996

    portfolio.append({
        'asset': asset['ticker'] if 'ticker' in asset else asset['symbol'],
        'rating': asset['rating'],
        'allocation': allocation_after_commission,
        'percentage': percentage
    })

    remaining_capital -= allocation_after_commission

# Нормализуем процентные доли, чтобы их сумма была равна 100%
total_percentage = sum(entry['percentage'] for entry in portfolio)

for entry in portfolio:
    entry['percentage'] = (entry['percentage'] / total_percentage) * 100

# Создаем DataFrame с данными портфолио
assets = [entry['asset'] for entry in portfolio]
allocations = [entry['allocation'] for entry in portfolio]
percentages = [entry['percentage'] for entry in portfolio]
ratings = [entry['rating'] for entry in portfolio]

df = pd.DataFrame({
        "Asset": assets,
        "Rating": ratings,
        "Allocation ($)": allocations,
        "Percentage (%)": percentages
})

# Сохраняем портфолио в файл CSV
file_name = "portfolio.csv"
df.to_csv(file_name, index=False)
print(f"Портфолио сохранено в файл: {file_name}")

# Построение круговой диаграммы для визуализации портфолио
plt.figure(figsize=(10, 10))
plt.pie(
    df["Percentage (%)"],
    labels=df["Asset"],
    autopct='%1.1f%%',
    startangle=140,
    wedgeprops={"edgecolor": "black"}
)
plt.title("Портфолио")
plt.show()

print(f"Нераспределенный капитал: {remaining_capital}")
