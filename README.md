Склонировать репозиторий
git clone https://github.com/nikstreha/pars-123sdjdbfaskl

Запуск через
docker compose up -d --build

далее документация по адресу
http://localhost:8000/docs

Курлом можно прозвонить
curl -X 'GET' \
  'http://0.0.0.0:8000/parsing/?part_number=asd&site=lcsc' \
  -H 'accept: application/json'

параметры для site:

octopart
digikey
mouser
lcsc
all
