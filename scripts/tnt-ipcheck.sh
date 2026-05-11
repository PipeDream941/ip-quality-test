#!/usr/bin/env bash
# Usage:
#   ./tnt-ipcheck.sh <node-label>          # test current proxy exit, append to log
#   ./tnt-ipcheck.sh --report              # print sorted summary of all tests
#   ./tnt-ipcheck.sh --reset               # wipe the log
#
# Workflow: switch node in TNTCloud client -> run with a label -> repeat -> --report.

set -u
PROXY="${HTTPS_PROXY:-http://127.0.0.1:6174}"
LOG="${TNT_IPCHECK_LOG:-$HOME/.tnt-ipcheck.tsv}"

case "${1:-}" in
  "")        echo "usage: $0 <node-label> | --report | --reset" >&2; exit 2 ;;
  --reset)   : > "$LOG"; echo "cleared $LOG"; exit 0 ;;
  --report)
    [ ! -s "$LOG" ] && { echo "no data in $LOG"; exit 0; }
    printf "%-22s %-16s %-3s %-8s %-30s %-3s %-3s %-3s %-12s %s\n" \
      NODE IP CC ASN COMPANY DC VPN PRX ABUSER ANTHROPIC
    sort -t$'\t' -k9,9g "$LOG" | awk -F'\t' '{
      printf "%-22s %-16s %-3s %-8s %-30.30s %-3s %-3s %-3s %-12s %s\n",
        $1,$2,$3,$4,$5,$6,$7,$8,$9,$10
    }'
    exit 0 ;;
esac

LABEL="$1"
echo "[*] testing exit via $PROXY (label: $LABEL)"

JSON=$(curl -s -x "$PROXY" --max-time 12 "https://api.ipapi.is/?q=") || JSON=""
if [ -z "$JSON" ]; then
  echo "[!] ipapi.is failed through proxy"
  exit 1
fi

ANTHROPIC_CODE=$(curl -s -x "$PROXY" -o /dev/null -w "%{http_code}" --max-time 8 https://api.anthropic.com)

read IP CC ASN COMPANY DC VPN PRX TOR ABUSE_COMPANY <<<"$(python3 - <<PY
import json,sys
d=json.loads('''$JSON''')
def b(x): return 'Y' if x else 'n'
asn=d.get('asn') or {}
co=d.get('company') or {}
loc=d.get('location') or {}
print(d.get('ip','-'), loc.get('country_code','-'), asn.get('asn','-'),
      (co.get('name','-') or '-').replace(' ','_'),
      b(d.get('is_datacenter')), b(d.get('is_vpn')), b(d.get('is_proxy')),
      b(d.get('is_tor')),
      (co.get('abuser_score') or '-').replace(' ','_'))
PY
)"

printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
  "$LABEL" "$IP" "$CC" "$ASN" "$COMPANY" "$DC" "$VPN" "$PRX" "$ABUSE_COMPANY" "$ANTHROPIC_CODE" \
  >> "$LOG"

echo
echo "  IP:        $IP  ($CC)"
echo "  ASN:       AS$ASN  $COMPANY"
echo "  flags:     datacenter=$DC vpn=$VPN proxy=$PRX tor=$TOR"
echo "  abuser:    $ABUSE_COMPANY"
echo "  anthropic: HTTP $ANTHROPIC_CODE  $([ "$ANTHROPIC_CODE" = "403" ] && echo '<-- GEO BLOCKED' || echo 'ok')"
echo "  -> appended to $LOG"
