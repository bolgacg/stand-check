"""Download the three public test-stand datasets into data/raw/.

    python3 -I study/fetch.py [sterenberg|dlr|delft ...]

Nothing here is redistributed by this repository except what the licences allow and
data/derived/ needs. Every file is checked against the checksum its publisher states
(Zenodo md5, zip CRC32) or, for GitHub, fetched from a pinned commit.

The Delft archive is 2 GB. It is read entry by entry with HTTP range requests and only the
pressure, valve-state and thermocouple channels are kept, so the full archive is never
written to disk.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths  # noqa: E402  (adds the library folders)
import hashlib, io, json, struct, time, urllib.request, zlib  # noqa: E402

import numpy as np

RAW = _paths.RAW

STERENBERG_SHA = '1bc832a4a362eef57493c53a33cf93ba2ee8b1e2'
STERENBERG_FILES = ['misc/31718_hotfire_datalog_trimmed.csv', 'misc/test_data.csv',
                    'misc/mnemonics.csv', 'license.txt']

DLR_RECORD = 'https://zenodo.org/api/records/15526459'
DLR_FILE = 'PS-LN2-Set1.7z'

DELFT_ZIP = ('https://data.4tu.nl/file/dbaa8f0f-59d2-4d58-8cc9-494af1b966f1/'
             'b62a7800-90f7-483e-ba8d-82d5fda3053a')
DELFT_SIZE = 2047641733


def get(url, rng=None, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'stand-check/1.0'})
            if rng:
                req.add_header('Range', 'bytes=%d-%d' % rng)
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if rng and len(data) != rng[1] - rng[0] + 1:
                raise IOError('short read %d of %d' % (len(data), rng[1] - rng[0] + 1))
            return data
        except Exception as e:  # network hiccups on a 2 GB archive are normal
            if k == tries - 1:
                raise
            print('  retry after', e, flush=True)
            time.sleep(3 * (k + 1))


def sterenberg():
    out = os.path.join(RAW, 'sterenberg')
    os.makedirs(out, exist_ok=True)
    for f in STERENBERG_FILES:
        data = get('https://raw.githubusercontent.com/nsternie/engine_controller/%s/%s' % (STERENBERG_SHA, f))
        open(os.path.join(out, os.path.basename(f)), 'wb').write(data)
        print('sterenberg', f, len(data), hashlib.sha256(data).hexdigest()[:16])


def dlr():
    import py7zr
    out = os.path.join(RAW, 'dlr')
    os.makedirs(out, exist_ok=True)
    meta = json.loads(get(DLR_RECORD))
    f = next(x for x in meta['files'] if x['key'] == DLR_FILE)
    path = os.path.join(out, DLR_FILE)
    if not os.path.exists(path) or hashlib.md5(open(path, 'rb').read()).hexdigest() != f['checksum'].split(':')[1]:
        data = get(f['links']['self'])
        assert hashlib.md5(data).hexdigest() == f['checksum'].split(':')[1], 'md5 mismatch'
        open(path, 'wb').write(data)
    print('dlr', DLR_FILE, f['size'], f['checksum'])
    with py7zr.SevenZipFile(path, 'r') as z:
        z.extractall(out)
    # The workbooks are slow to read, so convert each sheet once to a compressed array file.
    import glob
    import pandas as pd
    for xl in sorted(glob.glob(os.path.join(out, 'PS-LN2-Set1', 'PS-LN2-*', '*.xlsx'))):
        if xl.endswith('Geometry.xlsx'):
            continue
        npz = xl[:-5] + '.npz'
        if os.path.exists(npz):
            continue
        df = pd.read_excel(xl)
        np.savez_compressed(npz, **{str(c): df[c].to_numpy(float) for c in df.columns})
        os.remove(xl)
        print('  converted', os.path.basename(xl), df.shape, flush=True)


def zip_directory():
    """Read the zip's central directory from the end of the archive."""
    tail = get(DELFT_ZIP, (DELFT_SIZE - 65536 * 4, DELFT_SIZE - 1))
    eocd = tail.rfind(b'PK\x05\x06')
    n, cd_size, cd_off = struct.unpack('<HII', tail[eocd + 10:eocd + 20])
    cd = get(DELFT_ZIP, (cd_off, cd_off + cd_size - 1))
    entries, p = [], 0
    for _ in range(n):
        (sig, _vm, _vn, _fl, method, _t, _d, crc, csize, usize, nlen, xlen, clen,
         _dn, _ia, _ea, off) = struct.unpack('<IHHHHHHIIIHHHHHII', cd[p:p + 46])
        assert sig == 0x02014b50
        name = cd[p + 46:p + 46 + nlen].decode()
        entries.append(dict(name=name, method=method, crc=crc, csize=csize, usize=usize, off=off))
        p += 46 + nlen + xlen + clen
    return entries


def zip_entry(e):
    hdr = get(DELFT_ZIP, (e['off'], e['off'] + 29))
    nlen, xlen = struct.unpack('<HH', hdr[26:30])
    start = e['off'] + 30 + nlen + xlen
    comp = get(DELFT_ZIP, (start, start + e['csize'] - 1)) if e['csize'] else b''
    data = zlib.decompressobj(-15).decompress(comp) if e['method'] == 8 else comp
    assert zlib.crc32(data) & 0xffffffff == e['crc'], 'crc mismatch in ' + e['name']
    return data


def delft():
    from nptdms import TdmsFile
    out = os.path.join(RAW, 'delft')
    os.makedirs(out, exist_ok=True)
    entries = zip_directory()
    for e in entries:
        if e['name'] in ('README.md', 'analysis/src/data_class.py'):
            open(os.path.join(out, os.path.basename(e['name'])), 'wb').write(zip_entry(e))
    runs = sorted({e['name'].split('_', 1)[1][:-5] for e in entries
                   if e['name'].startswith('data/Highspeed/HighspeedData_')})
    by = {e['name']: e for e in entries}
    index = []
    for run in runs:
        dst = os.path.join(out, 'run_%s.npz' % run)
        hs, th = by['data/Highspeed/HighspeedData_%s.tdms' % run], by['data/Thermal/ThermalData_%s.tdms' % run]
        row = dict(run=run, highspeed_bytes=hs['usize'], thermal_bytes=th['usize'],
                   highspeed_crc='%08x' % hs['crc'], thermal_crc='%08x' % th['crc'])
        if os.path.exists(dst):
            z = np.load(dst, allow_pickle=False)
            row.update(json.loads(str(z['meta'])))
            index.append(row)
            continue
        arrays, meta = {}, {}
        try:
            f = TdmsFile.read(io.BytesIO(zip_entry(hs)))
            meta.update(title=str(f.properties.get('title', '')), description=str(f.properties.get('description', '')),
                        datetime=str(f.properties.get('datetime', '')))
            for g in ('State', 'PS data'):
                if g in [x.name for x in f.groups()]:
                    for c in f[g].channels():
                        arrays['hs/%s/%s' % (g, c.name)] = c[:]
                        if 'wf_increment' in c.properties:
                            meta['wf_increment/%s' % c.name] = float(c.properties['wf_increment'])
            t = TdmsFile.read(io.BytesIO(zip_entry(th)))
            for g in t.groups():
                for c in g.channels():
                    arrays['th/%s/%s' % (g.name, c.name)] = c[:]
        except Exception as ex:  # the archive holds a few files with a header and no data
            meta['read_error'] = repr(ex)[:200]
        meta['channels'] = sorted(arrays)
        np.savez_compressed(dst, meta=json.dumps(meta), **arrays)
        row.update(meta)
        index.append(row)
        print('delft', run, hs['csize'] // 1000000, 'MB', len(arrays), 'channels', meta.get('title', ''), flush=True)
    json.dump(index, open(os.path.join(out, 'index.json'), 'w'), indent=1)


if __name__ == '__main__':
    which = sys.argv[1:] or ['sterenberg', 'dlr', 'delft']
    for w in which:
        globals()[w]()
