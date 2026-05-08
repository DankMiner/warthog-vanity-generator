#!/usr/bin/env python3
# =====================================================================
#  Warthog Vanity CLI  v1.0.0
#  Creator: DankMiner
# =====================================================================

import argparse
import json
import sys
import time

import warthog_engine as eng


def main() -> int:
    p = argparse.ArgumentParser(
        description="Warthog (WART) vanity address generator. Creator: DankMiner.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="examples:\n"
               "  warthog_cli.py dank\n"
               "  warthog_cli.py deadbeef -n 3 -j 8\n"
               "  warthog_cli.py beef -o matches.jsonl\n",
    )
    p.add_argument("pattern",
                   help="hex prefix to match (0-9 a-f, max 40 chars)")
    p.add_argument("-i", "--insensitive", action="store_true",
                   help="(no-op for hex addresses; canonical form is lowercase)")
    p.add_argument("-n", "--count", type=int, default=1,
                   help="stop after this many matches (default 1)")
    p.add_argument("-j", "--workers", type=int, default=0,
                   help="CPU worker count (0 = cpu_count - 1)")
    p.add_argument("-o", "--output", default=None,
                   help="append matches to this file as JSON Lines")
    p.add_argument("--no-banner", action="store_true")
    args = p.parse_args()

    if eng.EC_BACKEND is None:
        sys.stderr.write("ERROR: install ecdsa or coincurve first.\n")
        return 2

    pattern = args.pattern.strip().lower()
    try:
        eng.validate_pattern(pattern, args.insensitive)
    except eng.PatternError as e:
        sys.stderr.write(f"{e}\n")
        return 2

    if args.workers <= 0:
        import multiprocessing as mp
        args.workers = max(1, mp.cpu_count() - 1)

    if not args.no_banner:
        print(eng.BANNER)

    info = eng.env_summary()
    diff = eng.difficulty(pattern, args.insensitive)
    print(f"  EC backend    : {info['ec_backend']}")
    print(f"  Hash backend  : {info['hash_backend']}")
    print(f"  GPU           : {info['gpu'] or '(none)'}")
    print(f"  Target prefix : {pattern}")
    print(f"  Workers       : {args.workers}")
    print(f"  Want matches  : {args.count}")
    print(f"  Difficulty    : ~1 in {eng.fmt_n(diff)} keys")
    print(f"  Encoding      : 48 hex chars  (20-byte payload + 4-byte SHA-256 checksum)")
    print()
    print("  Searching... press Ctrl+C to stop.")
    print("-" * 64)

    procs, results, stats, stop, _ = eng.spawn_workers(
        pattern, args.insensitive, args.workers)

    fp = open(args.output, "a", encoding="utf-8") if args.output else None
    found = 0
    tried = 0
    t0 = time.time()
    last_print = t0
    try:
        while found < args.count:
            try:
                while True:
                    _, n, _ = stats.get_nowait()
                    tried += n
            except Exception:
                pass
            try:
                hit = results.get(timeout=0.5)
                found += 1
                elapsed = time.time() - t0
                print()
                print(f"  [HIT {found}/{args.count}]  in {eng.fmt_eta(elapsed)} "
                      f"after ~{eng.fmt_n(tried)} keys")
                print(f"    Address    : {hit['address']}")
                print(f"    Private key: {hit['privkey_hex']}")
                print(f"    Pubkey     : {hit['pubkey_hex']}")
                print(f"    Import     : wart-wallet --restore {hit['privkey_hex']} "
                      f"-f my-wallet.json")
                if fp:
                    fp.write(json.dumps(hit) + "\n"); fp.flush()
            except Exception:
                now = time.time()
                if now - last_print >= 2.0:
                    elapsed = now - t0
                    rate = tried / elapsed if elapsed > 0 else 0.0
                    remaining = max(0, diff - tried)
                    eta = remaining / rate if rate > 0 else float("inf")
                    sys.stdout.write(
                        f"\r  tried {eng.fmt_n(tried)}  |  "
                        f"{eng.fmt_n(rate)}/s  |  "
                        f"elapsed {eng.fmt_eta(elapsed):>10}  |  "
                        f"eta {eng.fmt_eta(eta):>14}   "
                    )
                    sys.stdout.flush()
                    last_print = now
    except KeyboardInterrupt:
        print("\n  Stopping...")
    finally:
        eng.stop_workers(procs, stop)
        if fp: fp.close()

    print()
    print("-" * 64)
    print(f"  Done. {found} match(es) in {eng.fmt_eta(time.time()-t0)}, "
          f"~{eng.fmt_n(tried)} keys tried.")
    print("  ~ DankMiner ~")
    return 0 if found > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
