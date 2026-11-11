#!/bin/sh
# Python pour la recette SEO, sans rien installer à la main (macOS, Linux).
# 1. Un Python 3.10+ déjà présent sur le poste est utilisé tel quel.
# 2. Sinon, un Python privé (python-build-standalone, version figée, empreinte vérifiée) est
#    téléchargé une fois dans ~/.claude/recettage-seo/python : sans droits administrateur,
#    sans toucher au reste du poste.
# Dernière ligne affichée : PY=<commande à utiliser>.
set -u

tester() { "$1" -c "import sys; print('ok' if sys.version_info >= (3, 10) else 'vieux')" 2>/dev/null | grep -qx ok; }

dest="$HOME/.claude/recettage-seo/python"
prive="$dest/bin/python3"
if [ -x "$prive" ] && tester "$prive"; then echo "PY=$prive"; exit 0; fi

# Sur macOS, /usr/bin/python3 peut n'être qu'un lanceur qui propose d'installer les outils Xcode :
# on ne le retient que s'il répond vraiment.
for c in python3 python; do
  chemin=$(command -v "$c" 2>/dev/null) || continue
  if tester "$chemin"; then echo "PY=$chemin"; exit 0; fi
done

version=20261021
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64)  nom="cpython-3.12.15+$version-aarch64-apple-darwin-install_only.tar.gz"
                 empreinte=a18cc33862b53bd54a148c710def5375c1b47470cccedf817a19c2d211764584 ;;
  Darwin-x86_64) nom="cpython-3.12.15+$version-x86_64-apple-darwin-install_only.tar.gz"
                 empreinte=869e0b30959beccc616ce14907439f4d0b3170c5830a2362dade07f07b0ed3b8 ;;
  *) echo "ECHEC: installe Python 3.10 ou plus avec le gestionnaire de paquets du poste, puis relance."; exit 1 ;;
esac
url="https://github.com/astral-sh/python-build-standalone/releases/download/$version/$(echo "$nom" | sed 's/+/%2B/')"

echo "Python absent : téléchargement d'un Python privé pour la recette (25 Mo environ, une seule fois)..."
tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT
if ! curl -fsSL "$url" -o "$tmp/python.tar.gz"; then
  echo "ECHEC: téléchargement impossible. Un pare-feu bloque peut-être github.com : installe Python depuis https://www.python.org/downloads/ puis relance."
  exit 1
fi
calcul=$(shasum -a 256 "$tmp/python.tar.gz" | cut -d' ' -f1)
if [ "$calcul" != "$empreinte" ]; then
  echo "ECHEC: le fichier téléchargé n'a pas l'empreinte attendue : rien n'a été installé."
  exit 1
fi
tar -xzf "$tmp/python.tar.gz" -C "$tmp" || { echo "ECHEC: décompression impossible."; exit 1; }
mkdir -p "$(dirname "$dest")"
rm -rf "$dest"
mv "$tmp/python" "$dest"
tester "$prive" || { echo "ECHEC: le Python privé ne démarre pas."; exit 1; }
echo "Python privé installé."
echo "PY=$prive"
