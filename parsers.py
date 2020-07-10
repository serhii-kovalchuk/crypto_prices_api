import json
import requests
import ssl
import asyncio
import websockets

from abc import ABC, abstractmethod
from aiohttp import web
from websockets.exceptions import ConnectionClosedError


data = {}


class BaseWebsoketParser(ABC):
    exchange_market_name = None
    url = None

    def get_ssl_context(self):
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        return ssl_context

    def get_unified_pair_name(self, pair):
        names_aliases = (("BTC", "XBT"), ("DOGE", "XDG"))

        for origin_name, alias_name in names_aliases:
            pair = pair.replace(alias_name, origin_name)
        return pair.replace("/", "")

    def save_price(self, data, pair, price):
        if pair in data:
            data[pair][self.exchange_market_name] = price
        else:
            data[pair] = {self.exchange_market_name: price}

    @abstractmethod
    def on_message(self, message):
        pass

    async def subscribe(self, websocket):
        pass

    async def get_tickers(self, data):
        try:
            async with websockets.connect(self.url, ssl=self.get_ssl_context()) as websocket:
                print(f"Started {self.exchange_market_name} websocket parser")
                await self.subscribe(websocket)

                async for message in websocket:
                    self.on_message(message)

        except ConnectionClosedError:
            print(f"ConnectionClosedError on {self.exchange_market_name} websocket")
            await self.get_tickers(data)


class BinanceWebsoketParser(BaseWebsoketParser):
    exchange_market_name = "binance"
    url = "wss://stream.binance.com:9443/ws/!ticker@arr"

    def get_ask_bid_average_price(self, ticker_data):
        return (float(ticker_data["a"]) + float(ticker_data["b"])) / 2

    def proccess_tickers_data(self, data, message):
        tickers_list = json.loads(message)

        for ticker_data in tickers_list:
            pair = ticker_data["s"]
            price = {"price": self.get_ask_bid_average_price(ticker_data)}
            self.save_price(data, pair, price)

    def on_message(self, message):
        # print(message)
        self.proccess_tickers_data(data, message)


class KrakenWebsoketParser(BaseWebsoketParser):
    exchange_market_name = "kraken"
    url = "wss://ws.kraken.com/"

    def get_ask_bid_average_price(self, ticker_data):
        prices = ticker_data[1]
        return (float(prices["a"][0]) + float(prices["b"][0])) / 2

    def process_ticker_data(self, data, ticker_data):
        pair = self.get_unified_pair_name(ticker_data[-1])
        price = {"price": self.get_ask_bid_average_price(ticker_data)}
        self.save_price(data, pair, price)

    def on_message(self, message):
        # print(message)
        ticker_data = json.loads(message)
        if type(ticker_data) == list:
            self.process_ticker_data(data, ticker_data)

    # runs only once
    def get_pairs_names(self):
        r = requests.get("https://api.kraken.com/0/public/AssetPairs")
        pairs_dict = json.loads(r.text)['result']

        pairs_ws_names = ""

        for pair_name, pair_data in pairs_dict.items():
            try:
                pair_wsname = pair_data['wsname']
                pairs_ws_names += f'"{pair_wsname}",'
            except KeyError:
                pass

        if pairs_ws_names:
            pairs_ws_names = pairs_ws_names[:-1]  # removes ',' symbol
        return pairs_ws_names

    async def subscribe(self, websocket):
        pairs_names = self.get_pairs_names()
        await websocket.send('{"event":"subscribe", "subscription":{"name":"ticker"}, "pair":[' + pairs_names + ']}')


# HTTP SERVER TO COMMUNICATE WITH DJANGO APP

class HttpServerController:

    def _response(self, context):
        return web.Response(text=json.dumps(context))

    def success_response(self, result):
        context = {"status": "success", "data": result}
        return self._response(context)

    def error_response(self, error_code):
        context = {"status": "error", "error_code": error_code}
        return self._response(context)

    async def handle_get(self, request):
        try:
            pair = request.query["pair"].upper()
        except (KeyError, TypeError):
            pair = None

        try:
            source = request.query["source"].lower()
        except (KeyError, TypeError):
            source = None

        # gets requested data
        if pair and source:
            try:
                return self.success_response(data[pair][source])
            except KeyError:
                return self.error_response("unknown pair name or source")

        elif pair:
            try:
                return self.success_response(data[pair])
            except KeyError:
                return self.error_response("unknown pair name")

        elif source:
            if source not in (
                BinanceWebsoketParser.exchange_market_name,
                KrakenWebsoketParser.exchange_market_name
            ):
                return self.error_response("unknown source name")

            result = {}
            for pair_name, pair_data in data.items():
                if source in pair_data:
                    result[pair_name] = pair_data[source]
            return self.success_response(result)

        else:
            return self.success_response(data)


async def run_http_server():
    port = 8080
    app = web.Application()
    app.add_routes([web.get('/', HttpServerController().handle_get)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Started http server on {port}")


# CONCURRENT RUNNING OF PROGRAM COMPONENTS

asyncio.get_event_loop().run_until_complete(
    asyncio.gather(
        BinanceWebsoketParser().get_tickers(data),
        KrakenWebsoketParser().get_tickers(data),
        run_http_server(),
    )
)

