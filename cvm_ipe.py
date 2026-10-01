#!/usr/bin/env python3
"""Download Brazilian annual reports (CVM IPE register) for one year.

  index  https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_<year>.zip
  file   Link_Download -> https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?...

Kept types: Demonstrações Financeiras Anuais Completas, Demonstrações Financeiras em
Padrões Internacionais, Relatório Anual.
  python3 cvm_ipe.py --year 2023 --out out
"""
import argparse, csv, io, os, re, sys, threading, time, urllib.request, zipfile
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "Mozilla/5.0 (research; personal archive)"}
TYPES = {"Demonstrações Financeiras Anuais Completas",
         "Demonstrações Financeiras em Padrões Internacionais", "Relatório Anual"}
TYPES_OLD = TYPES | {"Press-release"}  # --source ipe for years before 2016: results releases too
EXT = {b"%PDF": ".pdf", b"PK\x03\x04": ".zip", b"<?xm": ".xml"}


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                return r.read(), r.headers.get("Content-Disposition") or ""
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(5 * (i + 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--out", default="out")
    ap.add_argument("--pause", type=float, default=0.5)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--source", default="ipe", choices=["ipe", "itr", "dfp"],
                    help="ipe: IPE register; itr/dfp: quarterly/annual statement documents (LINK_DOC)")
    a = ap.parse_args()

    if a.source == "ipe":
        z, _ = get(f"https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{a.year}.zip")
        zf = zipfile.ZipFile(io.BytesIO(z))
        rows = list(csv.DictReader(io.TextIOWrapper(zf.open(zf.namelist()[0]), "latin1"), delimiter=";"))
        types = TYPES if a.year >= 2016 else TYPES_OLD
        rows = [r for r in rows if r["Tipo"] in types and r["Link_Download"]]
    else:
        z, _ = get(f"https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/{a.source.upper()}/DADOS/"
                   f"{a.source}_cia_aberta_{a.year}.zip")
        zf = zipfile.ZipFile(io.BytesIO(z))
        raw = csv.DictReader(io.TextIOWrapper(zf.open(f"{a.source}_cia_aberta_{a.year}.csv"), "latin1"), delimiter=";")
        rows = [{"Nome_Companhia": r["DENOM_CIA"], "Codigo_CVM": r["CD_CVM"], "Data_Entrega": r["DT_RECEB"],
                 "Protocolo_Entrega": r["ID_DOC"], "Versao": r["VERSAO"], "Tipo": r["CATEG_DOC"],
                 "Especie": r["DT_REFER"], "Link_Download": r["LINK_DOC"].replace("http://", "https://").replace("/ENETCONSULTA/", "/ENET/")} for r in raw if r.get("LINK_DOC")]
    if a.limit:
        rows = rows[:a.limit]
    print(f"{a.year}: {len(rows)} documents", flush=True)
    st = {"ok": 0, "bad": 0, "n": 0}
    lock = threading.Lock()

    def one(r):
        name = re.sub(r"[^\w\-]+", "_", r["Nome_Companhia"])[:50].strip("_")
        folder = os.path.join(a.out, str(a.year), f"{r['Codigo_CVM']}_{name}")
        base = f"{r['Data_Entrega']}_{r['Protocolo_Entrega']}_v{r['Versao']}_" + \
               re.sub(r"[^\w\-]+", "_", r["Tipo"] + "_" + (r["Especie"] or ""))[:70].strip("_")
        try:
            time.sleep(a.pause)
            data, cd = get(r["Link_Download"])
            ext = EXT.get(data[:4]) or (os.path.splitext(cd.split("filename=")[-1].strip('"; '))[1] if "filename=" in cd else ".bin")
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, base + ext), "wb") as f:
                f.write(data)
            k = "ok"
        except Exception as e:
            k = "bad"
            print(f"  error {r['Protocolo_Entrega']}: {e}", file=sys.stderr, flush=True)
        with lock:
            st[k] += 1; st["n"] += 1
            if st["n"] % 100 == 0:
                print(f"[{st['n']}/{len(rows)}] ok={st['ok']} err={st['bad']}", flush=True)

    with ThreadPoolExecutor(a.threads) as ex:
        list(ex.map(one, rows))
    ok, bad = st["ok"], st["bad"]
    print(f"done {a.year}: ok={ok} err={bad}", flush=True)


if __name__ == "__main__":
    main()
