Projects implements multi service architecture. 
First servce is an asynchronous websocket parser, 
aimed to obtain last ticker data from 'Binance' and 'Kraken' services. 
Second is a simple django app, used as rest api service which provides currencies prices, 
obtained using parser app. Apps are deloyed in separate docker containers and communicates using simple http.

Api endpoint is 'localhost:8000/api/'. Example of request is 'localhost:8000/api/?pair=ADAETH&source=binance'