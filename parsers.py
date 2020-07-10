import time
import asyncio
import pathlib
import ssl
import websockets
import http.server
import socketserver

import json
import requests
import random

from aiohttp import web
from websockets.exceptions import ConnectionClosedError


data = {}


# UTILITES

def assign_prices(data, pair, source, prices):
	if pair in data:
		data[pair][source] = prices
	else:
		data[pair] = {source: prices}


def save_binance_tickers(data, message):
	price_types = ["c", "o", "h", "l"]
	tickers_list = json.loads(message)

	for ticker_data in tickers_list:
		pair = ticker_data["s"]
		prices = {price_type: ticker_data[price_type] for price_type in price_types}
		
		assign_prices(data, pair, "binance", prices)


def get_unified_name(pair):
	return pair.replace("/", "")		


def save_kraken_ticker(data, ticker_data):
	price_types = ["a", "c", "o", "h", "l"]

	def get_average_price(price_data):
		return (float(price_data[0]) + float(price_data[1])) / 2

	def get_first_price(price_data):
		return float(price_data[0])

	def get_price(ticker_data, price_type):
		price_get_methods = {
			"a": get_first_price, 
			"c": get_first_price, 
			"o": get_average_price, 
			"h": get_average_price, 
			"l": get_average_price
		}
		return price_get_methods[price_type](ticker_data[price_type])
	
	pair = get_unified_name(ticker_data[-1])
	prices = {price_type: get_price(ticker_data[1], price_type) for price_type in price_types}
		
	assign_prices(data, pair, "kraken", prices)


# runs only at the beginning
def get_kraken_pairs_names():
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
		pairs_ws_names = pairs_ws_names[:-1]   # remove ',' symbol
	return pairs_ws_names


# PAIRS PRICES PARSERS

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


async def get_binance_tickers(data):
	url = "wss://stream.binance.com:9443/ws/!ticker@arr"
	
	try:
		async with websockets.connect(url, ssl=ssl_context) as websocket:
			print("Started websocket binance parser")

			async for message in websocket:
				save_binance_tickers(data, message)
	
	except ConnectionClosedError:
		print("ConnectionClosedError on Binance websocket")
		await get_binance_tickers(data)


async def get_kraken_tickers(data):
	url = "wss://ws.kraken.com/"
	pairs_names = get_kraken_pairs_names()
	
	try:
		async with websockets.connect(url, ssl=ssl_context) as websocket:
			print("Started websocket kraken parser")

			await websocket.send('{"event":"subscribe", "subscription":{"name":"ticker"}, "pair":[' + pairs_names + ']}')
			
			async for message in websocket:
				ticker_data = json.loads(message)
				if type(ticker_data) == list:
					save_kraken_ticker(data, ticker_data)

	except ConnectionClosedError:
		print("ConnectionClosedError on Kraken websocket")
		await get_kraken_tickers(data)


# HTTP SERVER TO COMMUNICATE WITH DJANGO APP

async def run_http_server():

	async def handle_get(request):
		name = request.match_info.get('name', "Anonymous")
		pair = request.query.get("pair", None)
		source = request.query.get("source", None)

		# gets requested data
		if not pair and not source:
			result = data
		elif not source:
			result = data[pair]
		elif not pair:
			result = {}
			for pair_name, pair_data in data.items():
				if source in pair_data:
					result[pair_name] = pair_data[source]
		else:
			result = data[pair][source]

		return web.Response(text=json.dumps(result))

	port = 8080
	app = web.Application()
	app.add_routes([web.get('/', handle_get)])
	runner = web.AppRunner(app)
	await runner.setup()
	site = web.TCPSite(runner, '0.0.0.0', port)
	await site.start()
	print(f"Started http server on {port}")


# CONCURRENT RUNNING OF PROGRAM COMPONENTS

asyncio.get_event_loop().run_until_complete(
	asyncio.gather(   
		get_binance_tickers(data),
		get_kraken_tickers(data),
		run_http_server(),
	)
)

