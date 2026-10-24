# windblown-save-patcher

Small tool that sets MetaFlag bits in Windblown save files.
Made to get Guinea Pig and Intern, both were limited rewards for demo and early access players.

## How to use

Close game first.
Game keeps save in memory and rewrites file on next save point, so patch made while game runs gets lost.

Copy `config.example.yml` to `config.yml` and put your save path there.
Then run:

```
pipenv install
pipenv run python -m windblown_save_patcher --dry-run
pipenv run python -m windblown_save_patcher
```

Dry run only shows what would change.
Real run makes backup first and then writes save.

If Steam Cloud asks about conflict on next launch, pick local copy.

## Config

`config.yml` lives in project directory and git ignores it.

- `saves` - list of save files. `~` works, relative paths start from project directory.
- `flags` - flag name and bit number. Name goes only to log.
- `backup_directory` - optional. Without it backups go to `backups` in project directory.

With Proton saves live in `<steam library>/steamapps/compatdata/1911610/pfx/drive_c/users/steamuser/AppData/LocalLow/Motion Twin/Windblown/Steam_<steam id>/`.

## Which bits

Bit 91 is `PerpetualFlagDemoPlayer`, it gives Guinea Pig.
Bit 92 is `PerpetualFlagSuperEarlyAccessPlayer`, it gives Intern.

Checked on game build `ed587cc7d559d15a9c04c3358d5316aac5b1f390` from 2026-10-23.
Game update can move bits.
Patcher prints build of every save it touches.
Game writes names of set flags into `Player.log`, look for `PlayersMetaFlags` line.

## What happens to save

Patcher checks both SHA1 hashes, finds flag mask and sets missing bits.
Mask sits in up to three places: player save data, current run and biome start snapshot.
All copies get patched.
Unpatched run copy would bring old flags back when run resumes.
When all bits are already set, file stays untouched.

Before writing, original goes to `<backup_directory>/<timestamp>/<save folder>/`.
New file goes to temporary file first, then gets renamed over save.

To restore, close game and copy backup file back.

## Save file format

Nothing official here, layout below comes from poking at real saves.
Example is save with run in progress, 106782 bytes, numbers little-endian.

```
<player id>.sav
+-- 4d 54 57 42                     "MTWB" magic
+-- 01                              container version
+-- 2d 01 00 00                     header gzip length: 301
+-- <20 bytes>                      SHA1 of header gzip
+-- <301 bytes gzip>                header JSON, 485 bytes
|     {"PlayerId": "<player id>", "Alias": "<alias>", "Serial": 2420,
|      "LastUpdate": "2026-10-24T16:34:30Z", "BackHash": "...", ...}
+-- <20 bytes>                      SHA1 of all bytes below
+-- ed587cc7 ... 5316aac5b1f390     game build git hash, 20 bytes
+-- b8 09 00 63 00 07 00 00 30      0x09b8: build date, 2488 days after 2020-01-01
|                                   00 63 00: version bytes
|                                   0x30000007: save flags, 3 sections, save kind 3
+-- <106403 bytes gzip>             body, 130057 bytes
    +-- 9a 5f 00 00                 block size: 24474
    |   player save data            bit stream: schema (21 types), data
    |     root PlayerSaveData
    |     +-- assetFlags            dictionary, 549 entries
    |     +-- meta                  Quantum.PlayerMeta
    |     |   +-- _assets           dictionary, 594 entries
    |     |   +-- ...
    |     |   +-- flags._values     3 x uint64, MetaFlag mask, copy 1
    |     |   +-- species           asset guid
    |     +-- name                  "<alias>"
    |     +-- ...
    +-- 82 5e 00 00                 block size: 24194
    |   run frame                   bit stream: schema (44 types), data
    |     ... MetaFlag mask, copy 2
    +-- e1 3d 01 00                 block size: 81377
        biome start snapshot
        +-- 12 28 03 00             frame field
        +-- a8 19 01 00             nested gzip length: 72104
        +-- <72104 bytes gzip>      Quantum frame, 824104 bytes
        |     ... MetaFlag mask, copy 3
        +-- <9265 bytes>            trailer
```

Low 3 bits of save flags tell which blocks are there: 1 player save data, 2 run frame, 4 biome start snapshot.

### Bit stream

Player save data and run frame are bit streams.
Bits go LSB-first and values ignore byte boundaries.
Stream starts with schema, list of types with their fields.
Data follows in same field order.

This is how MetaFlag mask type looks in schema:

```
9-bit 51                  type header 0b000110011, low 3 bits 011: struct (010 enum, 100 class)
u16 20                    name length
"Quantum.MetaFlagMask"    name
u32 1                     field count
0                         unused bit
u16 7  "_values"          field name
8-bit 44                  fixed array
  8-bit 8                 element: uint64
  u32 3                   length
```

Other type codes: `0x40` + index (schema type), 40 array, 41 list, 42 dictionary (value type, key type), 43 set, 1 bool, 2 byte, 5 int32, 6 uint32, 7 int64, 8 uint64, 10 uint16, 11 string, 12 asset guid, 14 double.

And this is start of data for same save:

```
1                         assetFlags present
u16 549                   entry count
  64-bit key, 32-bit value, x549
0                         curMultiRunStats null
1                         curRunStats present
...
1                         meta present
  1  u16 594  ...         _assets: present, count, entries
  ...
  64 64 64                flags._values, fixed array: no header
  ...
0  u16 5  "<alias>"       name: null bit 0, length, UTF-8
```

Root record is last type in schema and has no presence bit.
Structs have no presence bit either.
Copies 2 and 3 have no fixed place, patcher finds them by exact value of copy 1.
