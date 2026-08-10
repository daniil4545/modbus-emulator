# AGENTS — modbus-emulator

Эмулятор Modbus-устройств для тестирования шлюза go-modbus2mqtt.
Статус: законсервирован на версии 1.0.0.

## Стек

Python 3.10+, pymodbus 3.9.2, pyserial 3.5, PyYAML 6.0.3. Виртуальное окружение в `venv/`.

## Команды

```bash
python main.py --check [template.yaml]   # проверить конфиг и показать карту регистров
python main.py [template.yaml]           # запуск; -q только ошибки, -v плюс чтения
python -m pytest -q                      # тесты
```

## Структура

| Файл | Ответственность |
|---|---|
| `main.py` | CLI, стартовая таблица, запись `devices.yaml`, `--check` |
| `generator.py` | разворот `count` из `template.yaml` |
| `config.py` | разбор и валидация конфига, `encode_value` / `decode_words` |
| `servers.py` | серверы, datastore, PTY, лог трафика через `trace_pdu` |
| `simulator.py` | обновление регистров с `sim:` |
| `template.yaml` | рабочий конфиг |
| `template.example.yaml` | справочник полей и примеры |

`devices.yaml` генерируется при каждом запуске и в git не хранится.

## Конфиг

Схема — это схема `Device` / `Register` из `go-modbus2mqtt/config_yaml.go` плюс
`test_value`, `sim`, `sim_tick`, `count`. Драйвер парсит YAML без `KnownFields`, поэтому
игнорирует лишние поля: один файл обслуживает и эмулятор, и драйвер. Менять схему —
значит менять её на обеих сторонах.

## Ловушки

- `ModbusSlaveContext.getValues/setValues` добавляет `+1` к адресу
  (`datastore/context.py:120`), поэтому запись в блок идёт по `address + 1`, а ячейка 0
  недостижима — размер блока считается с запасом на одну ячейку
- `ModbusSlaveContext.__init__` (`datastore/context.py:96-99`) проверяет наличие `co`,
  `ir` и `hr` через `if di is not None` — при отсутствии `di` три блока молча заменяются
  дефолтными. Всегда передавать все четыре
- У `ModbusSequentialDataBlock` в 3.9.2 нет проверки границ: `getValues` возвращает срез
  списка, за пределами блока — пустой. Для честного `ILLEGAL_DATA_ADDRESS` нужен
  подкласс, возвращающий int (`BoundedDataBlock` в `servers.py`); возврат int из
  `getValues` / `setValues` вызывающий код трактует как код исключения
- `ModbusSlaveContext.setValues` (`datastore/context.py:124-133`) не возвращает результат
  вызова блока, в отличие от `getValues` — код исключения теряется, и FC15/FC16 за
  границей блока выглядят успешными, хотя запись не произошла. Поэтому используется
  подкласс `SlaveContext` в `servers.py`, пробрасывающий возврат наверх
- `serve_forever()` (`server/base.py:78-87`) игнорирует результат `listen()`: при занятом
  порте сервер молча уходит в ожидание future, который уже некому разрешить, и процесс
  висит без диагностики. Поэтому `listen()` вызывается явно в `_listen` (`servers.py`)
- `ignore_missing_slaves=False` бесполезен: pymodbus отвечает
  `ExceptionResponse(0x00, ...)` с function code `0x80`, который клиент не декодирует.
  Используется `True` (молчание), а диагностика идёт своим логом на входящем PDU
- Транспорт pymodbus для serial асинхронный (`transport/transport.py:197`) — потоки для
  serial-серверов не нужны, всё живёт в одном event loop
- Регистр с `bit` требует `format: bool`: при любом другом формате драйвер сбрасывает
  `bit` (`config_yaml.go:160`). В datastore при этом кладётся всё слово

## Правила

- Код правится только по явной просьбе пользователя: профиль Foresight — пользователь
  пишет код сам, агент консультирует. Документацию агент ведёт сам
- Не коммитить без подтверждения
