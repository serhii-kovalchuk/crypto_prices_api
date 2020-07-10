Projects implements multi service architecture.
First service is an asynchronous websocket parser,
aimed to obtain last ticker data from 'Binance' and 'Kraken' services.
Second is a simple django app, used as rest api service which provides currencies prices,
obtained using parser app. Apps are deloyed in separate docker containers and communicates using simple http.

Local deployment:
    1. git clone https://github.com/serhii-kovalchuk/crypto_prices_api.git.
    2. cd crypto_prices_api.
    3. docker network create crypto_prices_api_network.
    4. docker-compose up --build.

Api endpoint is 'localhost:8000/api/'.
Example of request is 'localhost:8000/api/?pair=ADAETH&source=binance'

