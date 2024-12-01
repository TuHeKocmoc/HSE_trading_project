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
    print("Получаю объем транзакций и circulating supply...")
    url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}"
    response = requests.get(url)

    if response.status_code in [429, 503, 504]:
        retry_after = response.headers.get('Retry-After')
        wait_time = int(retry_after) if retry_after else 10
        print(f"Жду {wait_time} секунд перед повторной попыткой...")
        time.sleep(wait_time)
        return get_transaction_data(coingecko_id)
    elif response.status_code == 404:
        print("Проблема: ", response)
        return {
            "transaction_volume_usd": 0,
            "circulating_supply": 0
        }
    elif response.status_code != 200:
        raise Exception(
            f"Не удалось получить информацию для {coingecko_id}: "
            f"{response.status_code}")

    data = response.json()

    transaction_volume = (data.get("market_data", {})
                          .get("total_volume", {}).get("usd"))

    circulating_supply = (data.get("market_data", {})
                          .get("circulating_supply"))

    if transaction_volume is None:
        transaction_volume = 0
    if circulating_supply is None:
        circulating_supply = 0

    return {
        "transaction_volume_usd": transaction_volume,
        "circulating_supply": circulating_supply
    }


load_dotenv()

TOKEN = os.getenv("TOKEN")
api_key = os.getenv("API_KEY")
secret_key = os.getenv("SECRET_KEY")
passphrase = os.getenv("PASSPHRASE")
all_metrics = []
metrics_file = "all_metrics.csv"

if not all([TOKEN, api_key, secret_key, passphrase]):
    raise ValueError("Не все переменные окружения загружены. "
                     "Проверьте файл .env.")

print("Переменные успешно загружены из .env!")

if os.path.exists(metrics_file):
    print(f"Файл {metrics_file} уже существует. "
          f"Пропускаю обработку акций и криптовалют...")
    metrics_df = pd.read_csv(metrics_file)
else:
    print('Начинаю обрабатывать акции...')

    with (Client(TOKEN) as client):
        instruments = client.instruments.shares().instruments

        for stock in tqdm(instruments, desc="Акции", unit="акция"):
            flag = False
            while not flag:
                try:
                    figi = stock.figi
                    issue_size = stock.issue_size

                    history = client.market_data.get_candles(
                        figi=figi,
                        from_=datetime.now(timezone.utc) - timedelta(days=365),
                        to=datetime.now(timezone.utc),
                        interval=CandleInterval.CANDLE_INTERVAL_DAY
                    )

                    prices = [float(candle.close.units +
                                    candle.close.nano / 1e9)
                              for candle in history.candles]

                    if prices:
                        last_price = prices[-1]
                        returns = ((last_price - prices[0]) / prices[0]) * 100
                    else:
                        last_price = 0
                        returns = 0

                    if history.candles:
                        volumes = [candle.volume for candle in history.candles]
                        liquidity = np.mean(volumes)
                    else:
                        volumes = []
                        liquidity = 0

                    nominal_value = (stock.nominal.units +
                                     stock.nominal.nano / 1e9)
                    market_cap = last_price * issue_size
                    net_income = market_cap * 0.1  # 0.1 -- условная прибыль
                    eps = net_income / issue_size if issue_size else None
                    pe = last_price / eps if eps else None

                    if issue_size and nominal_value:
                        book_value = issue_size * nominal_value
                        book_value_per_share = book_value / issue_size
                        pb = last_price / book_value_per_share
                    else:
                        book_value = None
                        book_value_per_share = None
                        pb = None

                    if pe and pe < 15:
                        pe_score = 1
                    elif pe and pe < 25:
                        pe_score = 0.25
                    else:
                        pe_score = 0

                    if pb and pb < 1.5:
                        pb_score = 1
                    elif pb and pb < 3:
                        pb_score = 0.5
                    else:
                        pb_score = 0

                    returns_score = np.clip(returns / 10, 0, 1)
                    liquidity_score = np.clip(liquidity / 1_000_000, 0, 1)

                    total_score = (
                            0.4 * pe_score +
                            0.3 * pb_score +
                            0.2 * returns_score +
                            0.1 * liquidity_score
                    )

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
                    print("Проблема: ", e)
                    ratelimit_reset = 10
                    if e.metadata and hasattr(e.metadata, "ratelimit_reset"):
                        ratelimit_reset = int(e.metadata.ratelimit_reset)
                    print(f"Ожидание {ratelimit_reset} секунд...")
                    time.sleep(ratelimit_reset)

    print('Обработка акций завершена')
    print('Подключаюсь к API для криптовалют...')

    market_api = MarketAPI(api_key, secret_key, passphrase, False, '0')
    tickers = market_api.get_tickers(instType='SPOT')['data']

    print("OKX подключен...")

    cg = CoinGeckoAPI()
    coins = cg.get_coins_list()
    mapping = {coin['symbol']: coin['id'] for coin in coins}
    print("CoinGecko подключен...")

    print('Подключился')
    print('Начинаю обрабатывать криптовалюты...')

    for symbol in tqdm(tickers, desc="Криптовалюты", unit="пара"):
        flag = False
        while not flag:
            try:
                liquidity = float(symbol['vol24h'])
                price = float(symbol['last'])
                inst_id = symbol['instId']
                print("Получаю OKX дату...")
                response = market_api.get_candlesticks(instId=inst_id,
                                                       bar='1D')
                print("Получено...")
                data = response['data']

                columns = [
                    'timestamp', 'open', 'high', 'low', 'close',
                    'volume', 'quote_volume', 'redundant_quote_volume', 'flag'
                ]

                df = pd.DataFrame(data, columns=columns)

                df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int),
                                                 unit='ms')

                numeric_columns = ['open', 'high', 'low', 'close', 'volume',
                                   'quote_volume']

                df[numeric_columns] = df[numeric_columns].astype(float)

                df["pct_change"] = df["close"].pct_change()
                df["volatility"] = df["pct_change"].abs() * 100
                max_volatility = df["volatility"].max()

                if not df.empty:
                    returns = ((df['close'].iloc[-1] - df['close'].iloc[0])
                               / df['close'].iloc[0]) * 100
                    volatility = df['close'].pct_change().std() * 100
                else:
                    returns = 0
                    volatility = 0

                print("Получаю CoinGecko дату...")
                coingecko_id = mapping.get(inst_id.split('-')[0].lower(), None)
                coingecko_data = get_transaction_data(coingecko_id)
                print("Получено!")

                daily_transaction_volume = coingecko_data[
                    'transaction_volume_usd'
                ]
                circulating_supply = coingecko_data['circulating_supply']

                market_cap = price * circulating_supply

                print("Получено...")

                pv_ratio = price / liquidity if liquidity > 0 else None

                if daily_transaction_volume > 0:
                    nvt_ratio = market_cap / daily_transaction_volume
                    nvt_score = 1 / (nvt_ratio + 1)
                else:
                    nvt_ratio = None
                    nvt_score = 0

                returns_score = np.clip(returns / 10, 0, 1)
                liquidity_score = np.clip(liquidity / 1_000_000, 0, 1)

                pv_score = 1 / (pv_ratio + 1) if pv_ratio is not None else 0

                if max_volatility:
                    volatility_score = 1 - min(volatility / max_volatility, 1)
                else:
                    volatility_score = None

                total_score = (
                        0.3 * nvt_score +
                        0.2 * pv_score +
                        0.3 * returns_score +
                        0.1 * liquidity_score +
                        0.1 * volatility_score
                )

                all_metrics.append({
                    "symbol": inst_id,
                    "returns": returns,
                    "volatility": volatility,
                    "liquidity": liquidity,
                    "rating": total_score
                })
                flag = True
            except ReadTimeout as e:
                print("Проблема: ", e)
                print("Повторяю попытку...")
                time.sleep(10)
                continue

    print('Закончил обрабатывать криптовалюты')

    metrics_df = pd.DataFrame(all_metrics)
    metrics_df.to_csv(metrics_file, index=False, encoding="utf-8")

    print(f"Данные all_metrics сохранены в {metrics_file}")
print('Начинаю делать портфолио...')

total_capital = int(input("Введите капитал: "))

all_metrics.sort(key=lambda x: x['rating'], reverse=True)

filtered_assets = [asset for asset in all_metrics
                   if asset.get('liquidity', 0) >= 10_000]

max_capital_per_asset = total_capital * 0.3
portfolio = []

remaining_capital = total_capital

for asset in filtered_assets:
    if remaining_capital <= 0:
        break
    allocation = min(max_capital_per_asset,
                     remaining_capital / len(filtered_assets))

    allocation_after_commission = allocation * 0.9996

    portfolio.append({
        'asset': asset['ticker'] if 'ticker' in asset else asset['symbol'],
        'rating': asset['rating'],
        'allocation': allocation_after_commission,
        'percentage': allocation_after_commission / total_capital * 100
    })

    remaining_capital -= allocation

total_percentage = sum(entry['percentage'] for entry in portfolio)

for entry in portfolio:
    entry['percentage'] = (entry['percentage'] / total_percentage) * 100

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

file_name = "portfolio.csv"
df.to_csv(file_name, index=False)
print(f"Портфолио сохранено в файл: {file_name}")

threshold = 1
small_categories = df[df["Percentage (%)"] < threshold]
other_percentage = small_categories["Percentage (%)"].sum()
df = df[df["Percentage (%)"] >= threshold]
df = df.append({"Asset": "Other", "Percentage (%)": other_percentage},
               ignore_index=True)

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
