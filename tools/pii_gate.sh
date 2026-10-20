#!/usr/bin/env bash
# Refuse to publish if the tree holds personal data. Run before every push: tools/pii_gate.sh
cd "$(dirname "$0")/.." || exit 2
fail=0
hit() { echo "PII GATE: $1"; echo "$2" | head -20; fail=1; }
files=$(git ls-files -co --exclude-standard)
txt() { echo "$files" | grep -v -E '\.(jpg|jpeg|png|ttf|jar)$'; }
check() { # label, regex, [extra grep -v filter]
  local out; out=$(txt | xargs grep -n -I -E -i "$2" 2>/dev/null | grep -v -E "${3:-^$}" | grep -v '^tools/pii_gate.sh:')
  [ -z "$out" ] || hit "$1" "$out"
}
check "private IP"          '192\.168\.[0-9]|10\.[0-9]+\.[0-9]+\.[0-9]+:5555'
check "Wi-Fi name"          'titanic'
check "family name"         'goel family'
check "personal email"      'gmail|sarthak\.goel01'
check "employer"            'flobiz'
check "phone number"        '(^|[^0-9])(\+91[ -]?)?[6-9][0-9]{9}([^0-9]|$)'
check "photo dir"           'family-photos' '^\.gitignore:'
check "secret"              '(api[_-]?key|secret|token|passw(or)?d)["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"']{8,}|BEGIN [A-Z ]*PRIVATE KEY|gh[pousr]_[A-Za-z0-9]{20}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30}|sk-[A-Za-z0-9]{20}'
check "name outside allowed" 'sarthak' '^(LICENSE|README\.md):|cv\.sarthakgoel|sarthakgoel31/tv-glowup'
bad=$(echo "$files" | grep -E '(^|/)(backups|family-photos[^/]*|my-photos)/|\.apk$|(^|/)\.env|\.(jks|keystore|pem|p12)$|local\.properties$')
[ -z "$bad" ] || hit "forbidden files" "$bad"
bad=$(echo "$files" | grep -E '(^|/)(dream[^/]*\.png|photos_sheet\.jpg)$')
[ -z "$bad" ] || hit "forbidden screenshots" "$bad"
[ $fail = 0 ] && echo "PII gate: clean ($(echo "$files" | wc -l | tr -d ' ') files)"
exit $fail
