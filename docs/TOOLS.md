# Инструменты разбора ROM Yealink T4xU

Каталог: `E:\0ai\yealink_t4xu\tools` (рабочая копия — WSL `~/re/samples/yealink-t4xu`).
Требуется Python 3 + `pycryptodome` не нужен; нужен только `lzma` (stdlib) и `zlib` (stdlib).

## romtool.py — чтение

```bash
python3 romtool.py old/108.86.0.118.rom old/108.86.0.154.rom
```

Печатает: версию, crypto_type, `length`, размер хвоста, таблицу блоков (offset, total, length, type, cipher).

API:

```python
from romtool import hdr, blocks, c3
H = hdr(data)            # поля заголовка ROM
bl, end = blocks(data)   # список блоков + конец цепочки
plain = c3(wire)         # расшифровка cypher3 (одна операция)
```

## rompack.py — пересборка «как есть»

```bash
python3 rompack.py old/108.86.0.118.rom /tmp/rt.rom
```

Собирает ROM из исходных байтов, пересчитывает `length` = сумма `block_total` и `header_crc` = zlib CRC32 по 0x80 с обнулённым полем. Хвост копируется как есть.
Проверка: выход должен совпасть с входом байт в байт (для `.118` и `.20` — совпадает).

## romblock.py — послойное кодирование

```bash
python3 romblock.py old/108.86.0.118.rom
```

Для каждого блока: `decode` (внешний cypher3 + внутренний слой по `cipher`) и `encode` обратно; печатает, совпал ли результат с оригиналом.

- `cipher=0` — совпадает;
- `cipher=3` — совпадает;
- `cipher=1` — **не совпадает** (другой liblzma), но `decode(encode(x)) == x`.

## rombuild.py — сборка с заменой блоков

```python
import rombuild
from romtool import blocks

d = open('old/108.86.0.118.rom','rb').read()
bl,_ = blocks(d)
b = [x for x in bl if x['name']=='bootloader'][0]
plain = rombuild.inner_dec(d[b['off']+0x80 : b['off']+0x80+b['length']], b['cipher'])
plain = plain[:0x100] + bytes([plain[0x100]^0xff]) + plain[0x101:]
out = rombuild.build(d, {'bootloader': plain})
open('/tmp/mod.rom','wb').write(out)
```

Правила внутри `build`:
- неизменённые блоки копируются побайтово (гарантия идентичности);
- изменённый блок: внутренний слой по `cipher` → `block_total = align32(0x80+len)` → паддинг нулями → внешний cypher3 на весь блок;
- `length` заголовка блока = длина тела, `header_crc` блока пересчитывается;
- заголовок ROM: `length` = сумма totals, `header_crc` пересчитывается;
- хвост (если есть) переносится без изменений.

Проверка после сборки:

```python
from romtool import blocks
bl2,_ = blocks(out)          # таблица блоков читается
# payload: rombuild.inner_dec(out[off+0x80:...], cipher) == plain
```

## rebuild.py — воспроизводимая сборка (CLI)

```bash
python3 rebuild.py old/108.86.0.118.rom -o out.rom
python3 rebuild.py old/108.86.0.118.rom -o out.rom --version 108.86.0.119
python3 rebuild.py src.rom -o out.rom --replace bootloader=uboot_plain.bin
```

Печатает размер, версию, `length`, хвост, CRC заголовка и каждого блока, SHA-256 результата.

Проверено (2026-10-29):

| сборка | SHA-256 | результат |
|---|---|---|
| `.118` без изменений | `ff0945…14d2a7` | совпадает с исходником |
| `.118` + версия `108.86.0.119` | `16e7fff6…2a1deaf9` | совпадает с ранее собранным артефактом |
| `.20` + версия `108.87.0.21` | `c3771f89…fa87b2b9` | совпадает, хвост 512 Б сохранён |

То есть сборка детерминирована: один и тот же вход → один и тот же файл.

## Ограничения

1. LZMA-поток пересобранного `rfs` не побайтово равен вендорскому (наш liblzma). Формат совместим (FORMAT_ALONE, dict 0x40000, lc3/lp0/pb2), но совместимость декодера проверяется только на устройстве.
2. Хвост 512 Б не пересчитывается и не переподписывается — копируется.
3. AES-256 (`cipher=0x83`) не реализован: ключ не найден.

## ubi_extract.py

Собирает тома из `rfs`-блока пакета или из дампа: разбирает EC/VID-заголовки, сортирует LEB по `lnum`, пишет по файлу на том.

```bash
python3 tools/ubi_extract.py old/108.86.0.118.rfs.bin --out /tmp/ubi_out
```

Проверено на `108.86.0.118`: 333 PEB, том `rootfs` — 331 LEB по `0x1F000`, служебный том `0x7FFFFFFF` — 2 LEB.
