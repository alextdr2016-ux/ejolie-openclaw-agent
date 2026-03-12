#!/bin/bash
# ================================================================
# Setup: Agent Localități Geo pe EC2
# ================================================================
# Rulează: bash setup_localitati_agent.sh
# 
# Ce face:
#   1. Copiază scriptul Python în scripts/
#   2. Creează agentul OpenClaw
#   3. Copiază SOUL.md
#   4. Copiază auth profiles de la main agent
#   5. Testează scriptul cu un query mic
# ================================================================

set -e

echo "========================================"
echo "  Setup Agent Localități Geo"
echo "========================================"

# Paths
SCRIPTS_DIR="$HOME/ejolie-openclaw-agent/ejolie-sales/scripts"
AGENT_NAME="localitati-geo"
AGENT_DIR="$HOME/.openclaw/agents/${AGENT_NAME}/agent"
MAIN_AUTH="$HOME/.openclaw/agents/main/agent/auth-profiles.json"

# 1. Copiază scriptul
echo ""
echo "[1/5] Copiez scriptul Python..."
cp localitati_overpass.py "$SCRIPTS_DIR/"
chmod +x "$SCRIPTS_DIR/localitati_overpass.py"
echo "  ✓ Copiat în $SCRIPTS_DIR/"

# 2. Instalează dependințe
echo ""
echo "[2/5] Verific dependințe Python..."
pip3 install requests openpyxl --quiet 2>/dev/null || pip install requests openpyxl --quiet 2>/dev/null
echo "  ✓ requests + openpyxl OK"

# 3. Creează agentul OpenClaw
echo ""
echo "[3/5] Creez agentul OpenClaw..."
if [ -d "$AGENT_DIR" ]; then
    echo "  ⚠ Agentul '$AGENT_NAME' există deja. Actualizez SOUL.md..."
else
    # Creează structura agentului
    mkdir -p "$AGENT_DIR"
    echo "  ✓ Director agent creat: $AGENT_DIR"
fi

# 4. Copiază SOUL.md
cp localitati-agent-SOUL.md "$AGENT_DIR/SOUL.md"
echo "  ✓ SOUL.md copiat"

# 5. Copiază auth profiles
if [ -f "$MAIN_AUTH" ]; then
    cp "$MAIN_AUTH" "$AGENT_DIR/auth-profiles.json"
    echo "  ✓ Auth profiles copiate de la main"
else
    echo "  ⚠ Auth profiles main nu există la $MAIN_AUTH"
    echo "    Trebuie configurate manual."
fi

# 6. Creează directorul output
mkdir -p /tmp/localitati
echo "  ✓ Director output: /tmp/localitati"

# 7. Test rapid
echo ""
echo "[4/5] Test rapid (Iași, 10km, doar orașe)..."
cd "$SCRIPTS_DIR"
python3 localitati_overpass.py --oras iasi --raza 10 --tip city,town --format csv --output-dir /tmp/localitati 2>&1 || {
    echo "  ⚠ Testul a eșuat. Verifică conexiunea la internet."
    echo "  Poți testa manual: python3 $SCRIPTS_DIR/localitati_overpass.py --oras iasi --raza 10"
}

# Rezumat
echo ""
echo "========================================"
echo "  ✅ SETUP COMPLET"
echo "========================================"
echo ""
echo "  Script:  $SCRIPTS_DIR/localitati_overpass.py"
echo "  Agent:   $AGENT_NAME"
echo "  SOUL.md: $AGENT_DIR/SOUL.md"
echo "  Output:  /tmp/localitati/"
echo ""
echo "  UTILIZARE DIRECTĂ:"
echo "    python3 $SCRIPTS_DIR/localitati_overpass.py --oras iasi --raza 100"
echo ""
echo "  UTILIZARE VIA OPENCLAW:"
echo "    openclaw chat --agent $AGENT_NAME"
echo "    > localitati iasi 100"
echo ""
echo "  UTILIZARE VIA TELEGRAM:"
echo "    Trimite la @fabrexbot: localitati iasi 100"
echo ""
echo "========================================"